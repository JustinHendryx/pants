# coding=utf-8
# Copyright 2015 Pants project contributors (see CONTRIBUTORS.md).
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import (absolute_import, division, generators, nested_scopes, print_function,
                        unicode_literals, with_statement)

import collections
from abc import abstractproperty

from pants.engine.exp.fs import Files as FSFiles
from pants.engine.exp.fs import PathGlobs
from pants.engine.exp.objects import Locatable
from pants.engine.exp.struct import StructWithDeps
from pants.source import wrapped_globs
from pants.util.meta import AbstractClass


class TargetAdaptor(StructWithDeps, Locatable):
  """A Struct to imitate the existing Target.

  Extending StructWithDeps causes the class to have a `dependencies` field marked Addressable.
  """

  @property
  def sources_base_globs(self):
    """Return a BaseGlobs for this Target's sources."""
    if getattr(self, 'sources', None) is None:
      return Files()
    elif isinstance(self.sources, BaseGlobs):
      return self.sources
    elif isinstance(self.sources, collections.Sequence):
      return Files(*self.sources)
    else:
      raise ValueError('TODO: Could not construct PathGlobs from {}'.format(self.sources))

  @property
  def sources_path_globs(self):
    """Converts captured `sources` arguments to a PathGlobs object.

    This field may be projected to request files or file content for the paths in the sources field.
    """
    return self.sources_base_globs.to_path_globs(self.spec_path)


class BaseGlobs(AbstractClass):
  """An adaptor class to allow BUILD file parsing from ContextAwareObjectFactories."""

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