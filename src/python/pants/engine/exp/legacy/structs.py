# coding=utf-8
# Copyright 2015 Pants project contributors (see CONTRIBUTORS.md).
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import (absolute_import, division, generators, nested_scopes, print_function,
                        unicode_literals, with_statement)

import collections
from abc import abstractproperty

from pants.build_graph.address import Addresses
from pants.engine.exp.addressable import Exactly, addressable_list
from pants.engine.exp.fs import Files as FSFiles
from pants.engine.exp.fs import PathGlobs
from pants.engine.exp.struct import Struct, StructWithDeps
from pants.source import wrapped_globs
from pants.util.meta import AbstractClass
from pants.util.objects import datatype


class TargetAdaptor(StructWithDeps):
  """A Struct to imitate the existing Target.

  Extends StructWithDeps to add a `dependencies` field marked Addressable.
  """

  @property
  def has_concrete_sources(self):
    """Returns true if this target has non-deferred sources.

    NB: once ivy is implemented in the engine, we can fetch sources natively here, and/or
    refactor how deferred sources are implemented.
      see: https://github.com/pantsbuild/pants/issues/2997
    """
    sources = getattr(self, 'sources', None)
    return sources is not None and not isinstance(sources, Addresses)

  @property
  def field_adaptors(self):
    """Returns a tuple of Fields for captured fields which need additional treatment."""
    if not self.has_concrete_sources:
      return tuple()
    base_globs = BaseGlobs.from_sources_field(self.sources)
    path_globs = base_globs.to_path_globs(self.address.spec_path)
    return (SourcesField(self.address, base_globs.filespecs, path_globs),)


class Field(object):
  """A marker for Target(Adaptor) fields for which the engine might perform extra construction."""


class SourcesField(datatype('SourcesField', ['address', 'filespecs', 'path_globs']), Field):
  """Represents the `sources` argument for a particular Target.

  Sources are currently eagerly computed in-engine in order to provide the `BuildGraph`
  API efficiently; once tasks are explicitly requesting particular Products for Targets,
  lazy construction will be more natural.
  """

  def __eq__(self, other):
    return type(self) == type(other) and self.address == other.address

  def __ne__(self, other):
    return not (self == other)

  def __hash__(self):
    return hash(self.address)


class BundlesField(datatype('BundlesField', ['address', 'bundles', 'filespecs_list', 'path_globs_list']), Field):
  """Represents the `bundles` argument, each of which has a PathGlobs to represent its `fileset`."""

  def __eq__(self, other):
    return type(self) == type(other) and self.address == other.address

  def __ne__(self, other):
    return not (self == other)

  def __hash__(self):
    return hash(self.address)


class BundleAdaptor(Struct):
  """A Struct to capture the args for the `bundle` object.

  Bundles have filesets which we need to capture in order to execute them in the engine.

  TODO: Bundles should arguably be Targets, but that distinction blurs in the `exp` examples
  package, where a Target is just a collection of configuration.
  """


class JvmAppAdaptor(TargetAdaptor):
  def __init__(self, bundles=None, **kwargs):
    """
    :param list bundles: A list of `BundleAdaptor` objects
    """
    super(JvmAppAdaptor, self).__init__(**kwargs)
    self.bundles = bundles

  @addressable_list(Exactly(BundleAdaptor))
  def bundles(self):
    """The BundleAdaptors for this JvmApp."""
    return self.bundles

  @property
  def field_adaptors(self):
    field_adaptors = super(JvmAppAdaptor, self).field_adaptors
    if getattr(self, 'bundles', None) is None:
      return field_adaptors
    # Construct a field for the `bundles` argument.
    filespecs_list = []
    path_globs_list = []
    for bundle in self.bundles:
      base_globs = BaseGlobs.from_sources_field(bundle.fileset)
      filespecs_list.append(base_globs.filespecs)
      path_globs_list.append(base_globs.to_path_globs(self.address.spec_path))
    bundles_field = BundlesField(self.address,
                                 self.bundles,
                                 filespecs_list,
                                 path_globs_list)
    return field_adaptors + (bundles_field,)


class BaseGlobs(AbstractClass):
  """An adaptor class to allow BUILD file parsing from ContextAwareObjectFactories."""

  @staticmethod
  def from_sources_field(sources):
    """Return a BaseGlobs for the given sources field.

    Sources may be None, a sequence, or a BaseGlobs instance.
    """
    if sources is None:
      return Files()
    elif isinstance(sources, collections.Sequence):
      return Files(*sources)
    elif isinstance(sources, BaseGlobs):
      return sources
    else:
      raise AssertionError('Could not construct PathGlobs from {}'.format(sources))

  @abstractproperty
  def path_globs_kwarg(self):
    """The name of the `PathGlobs` parameter corresponding to this BaseGlobs instance."""

  @abstractproperty
  def legacy_globs_class(self):
    """The corresponding `wrapped_globs` class for this BaseGlobs."""

  def __init__(self, *patterns, **kwargs):
    self.filespecs = self.legacy_globs_class.to_filespec(patterns)
    if kwargs:
      # TODO
      raise ValueError('kwargs not supported for {}. Got: {}'.format(type(self), kwargs))

  def to_path_globs(self, relpath):
    """Return a PathGlobs object representing this BaseGlobs class."""
    return PathGlobs.create_from_specs(FSFiles, relpath, self.filespecs.get('globs', []))


class Files(BaseGlobs):
  path_globs_kwarg = 'files'
  legacy_globs_class = wrapped_globs.Globs


class Globs(BaseGlobs):
  path_globs_kwarg = 'globs'
  legacy_globs_class = wrapped_globs.Globs


class RGlobs(BaseGlobs):
  path_globs_kwarg = 'rglobs'
  legacy_globs_class = wrapped_globs.RGlobs


class ZGlobs(BaseGlobs):
  path_globs_kwarg = 'zglobs'
  legacy_globs_class = wrapped_globs.ZGlobs