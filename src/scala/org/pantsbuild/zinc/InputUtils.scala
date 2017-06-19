/**
 * Copyright (C) 2012 Typesafe, Inc. <http://www.typesafe.com>
 */

package org.pantsbuild.zinc

import java.io.{File, IOException}
import java.util.{ List => JList, Map => JMap }

import scala.collection.JavaConverters._

import sbt.util.Logger
import xsbti.{F1, Position}
import xsbti.compile.{
  CompileOrder,
  CompileOptions,
  Compilers,
  Inputs,
  PreviousResult
}

object InputUtils {
  /**
   * Create Inputs based on command-line settings.
   */
  def create(settings: Settings, previousResult: PreviousResult, log: Logger): Inputs = {
    import settings._

    // TODO: unused?
    val progress =
      new SimpleCompileProgress(
        consoleLog.logPhases,
        consoleLog.printProgress,
        consoleLog.heartbeatSecs
      )(log)

    val analysisMap = AnalysisMap.create(cacheMap, log)

    val compilers = CompilerUtils.getOrCreate(settings, log)

    val compileOptions =
      new CompileOptions(
        autoClasspath(
          classesDirectory,
          compilers.scalac().scalaInstance().allJars,
          javaOnly,
          classpath
        ).toArray,
        sources.toArray,
        classesDirectory,
        scalacOptions.toArray,
        javacOptions.toArray,
        Int.MaxValue,
        // Noop `sourcePositionMapper`.
        new F1[Position, Position] {
          override def apply(p: Position): Position = p
        },
        compileOrder
      )

    new Inputs(
      compilers,
      compileOptions,
      ???,
      previousResult
    )
  }

  /**
   * Automatically add the output directory and scala library to the classpath.
   */
  def autoClasspath(classesDirectory: File, allScalaJars: Seq[File], javaOnly: Boolean, classpath: Seq[File]): Seq[File] = {
    if (javaOnly) classesDirectory +: classpath
    else splitScala(allScalaJars) match {
      case Some(scalaJars) => classesDirectory +: scalaJars.library +: classpath
      case None            => classesDirectory +: classpath
    }
  }

  /**
   * Select the scala jars.
   *
   * Prefer the explicit scala-compiler, scala-library, and scala-extra settings,
   * then the scala-path setting, then the scala-home setting. Default to bundled scala.
   */
  def selectScalaJars(scala: ScalaLocation): ScalaJars = {
    val jars = splitScala(scala.path) getOrElse Defaults.scalaJars
    ScalaJars(
      scala.compiler getOrElse jars.compiler,
      scala.library getOrElse jars.library,
      scala.extra ++ jars.extra
    )
  }

  /**
   * Distinguish the compiler and library jars.
   */
  def splitScala(jars: Seq[File], excluded: Set[String] = Set.empty): Option[ScalaJars] = {
    val filtered = jars filterNot (excluded contains _.getName)
    val (compiler, other) = filtered partition (_.getName matches ScalaCompiler.pattern)
    val (library, extra) = other partition (_.getName matches ScalaLibrary.pattern)
    if (compiler.nonEmpty && library.nonEmpty) Some(ScalaJars(compiler(0), library(0), extra)) else None
  }

  //
  // Default setup
  //

  val ScalaCompiler            = JarFile("scala-compiler")
  val ScalaLibrary             = JarFile("scala-library")
  val ScalaReflect             = JarFile("scala-reflect")
  val CompilerBridgeSources    = JarFile("compiler-bridge", "sources")
  val CompilerInterface        = JarFile("compiler-interface")

  // TODO: The default jar locations here are definitely not helpful, but the existence
  // of "some" value for each of these is assumed in a few places. Should remove and make
  // them optional to more cleanly support Java-only compiles.
  object Defaults {
    val scalaCompiler        = ScalaCompiler.default
    val scalaLibrary         = ScalaLibrary.default
    val scalaExtra           = Seq(ScalaReflect.default)
    val scalaJars            = ScalaJars(scalaCompiler, scalaLibrary, scalaExtra)
    val scalaExcluded = Set("jansi.jar", "jline.jar", "scala-partest.jar", "scala-swing.jar", "scalacheck.jar", "scalap.jar")
  }

  /**
   * Jar file description for locating jars.
   */
  case class JarFile(name: String, classifier: Option[String] = None) {
    val versionPattern = "(-.*)?"
    val classifierString = classifier map ("-" + _) getOrElse ""
    val extension = "jar"
    val pattern = name + versionPattern + classifierString + "." + extension
    val default = new File(name + classifierString + "." + extension)
  }

  object JarFile {
    def apply(name: String, classifier: String): JarFile = JarFile(name, Some(classifier))
  }

  /**
   * The scala jars split into compiler, library, and extra.
   */
  case class ScalaJars(compiler: File, library: File, extra: Seq[File])
}
