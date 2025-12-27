package jp.kobe_u.bsaf

import scopt.OParser

import bn.BooleanNetwork
import sbml.SbmlQualModel
import encoder._

object Main {
  def main(args: Array[String]): Unit = {
    parseArgs(args) match {
      case Some(config) => {
        println(s"\n${config}\n")

        val e =
          if (config.tseitin) TseitinEncoder
          else if (config.tseitinProj) TseitinProjEncoder
          else if (config.pi) PIEncoder
          else if (config.hybrid1) HybridEncoder1
          else if (config.hybrid2) HybridEncoder2
          else HybridEncoder3

        val (sp, m) =
          if (config.sbmlFileName.nonEmpty)
            e.encodeSbmlQualModel(SbmlQualModel.fromFile(config.sbmlFileName))
          else
            e.encodeBooleanNetwork(BooleanNetwork.fromBnetFile(config.bnetFileName))

        println(m)
        sp.showDIMACS()
        if (config.tseitinProj)
          sp.dumpProj(config.cnfFileName, m.values.toSeq.sorted)
        else
          sp.dump(config.cnfFileName)
      }

      case _ => {
        sys.exit()
      }
    }
  }

  def parseArgs(args: Array[String]): Option[Config] = {
    val builder = OParser.builder[Config]
    val parser = {
      import builder._
      OParser.sequence(
        opt[String]("sbml")
          .action((x, c) => c.copy(sbmlFileName = x))
          .text("input SBML file"),
        opt[String]("bnet")
          .action((x, c) => c.copy(bnetFileName = x))
          .text("input BNET file"),
        opt[String]("cnf")
          .action((x, c) => c.copy(cnfFileName = x))
          .text("output CNF file [out.cnf]"),
        opt[Unit]('t', "tseitin")
          .action((_, c) => c.copy(tseitin = true))
          .text("use Tseitin (equiv) encoding"),
        opt[Unit]("tseitin_proj")
          .abbr("tp")
          .action((_, c) => c.copy(tseitinProj = true))
          .text("use Tseitin encoding"),
        opt[Unit]('p', "pi")
          .action((_, c) => c.copy(pi = true))
          .text("use PI encoding"),
        opt[Unit]("hybrid_1")
          .abbr("h1")
          .action((_, c) => c.copy(hybrid1 = true))
          .text("use Hybrid1 encoding"),
        opt[Unit]("hybrid_2")
          .abbr("h2")
          .action((_, c) => c.copy(hybrid2 = true))
          .text("use Hybrid2 encoding"),
        opt[Unit]("hybrid_3")
          .abbr("h3")
          .action((_, c) => c.copy(hybrid3 = true))
          .text("use Hybrid3 encoding [default]"),
        help('h', "help")
          .text("prints this usage text"),
        checkConfig(c =>
          if (Seq(c.sbmlFileName, c.bnetFileName).count(_.nonEmpty) == 1) success
          else failure("Exactly one input file is allowed")
        ),
        checkConfig(c =>
          if (Seq(c.tseitin, c.tseitinProj, c.pi, c.hybrid1, c.hybrid2, c.hybrid3).count(identity) <= 1) success
          else failure("Only one encoding method is allowed")
        )
      )
    }

    OParser.parse(parser, args, Config())
  }
}

case class Config(
    sbmlFileName: String = "",
    bnetFileName: String = "",
    cnfFileName: String = "out.cnf",
    tseitin: Boolean = false,
    tseitinProj: Boolean = false,
    pi: Boolean = false,
    hybrid1: Boolean = false,
    hybrid2: Boolean = false,
    hybrid3: Boolean = false
)
