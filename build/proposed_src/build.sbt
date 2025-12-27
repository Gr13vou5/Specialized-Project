name := "bsaf"

version := "1.0"

scalaVersion := "2.12.19"

libraryDependencies ++= Seq(
  compilerPlugin("org.polyvariant" % "better-tostring" % "0.3.17" cross CrossVersion.full),
  "com.github.scopt" %% "scopt" % "4.1.0",
  "org.sbml.jsbml" % "jsbml" % "1.6.1",
  "org.scala-lang.modules" %% "scala-parser-combinators" % "2.4.0"
)

assemblyMergeStrategy := {
  case x if x.endsWith("Log4j2Plugins.dat") => MergeStrategy.last
  case PathList("log4j2.xml")               => MergeStrategy.last
  case x                                    => assemblyMergeStrategy.value(x)
}
