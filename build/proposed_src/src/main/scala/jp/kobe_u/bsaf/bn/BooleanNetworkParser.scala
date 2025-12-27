package jp.kobe_u.bsaf.bn

import jp.kobe_u.bsaf.util._

import scala.collection.immutable.IndexedSeq
import scala.util.parsing.combinator._

abstract class BooleanNetworkParser extends JavaTokenParsers {
  var vars = Set.empty[String]
  var transitions = IndexedSeq.empty[Transition]

  def symbols = """[-_a-zA-Z0-9]+""".r

  def parse(fileName: String): BooleanNetwork

  def orDef: Parser[Expression]
  def andDef: Parser[Expression]
  def negDef: Parser[Expression]
  def conjunctDef: Parser[Expression]
  def literalDef: Parser[Literal]
  def varDef: Parser[String]
  def transitionDef: Parser[Transition]
}

object BnetParser extends BooleanNetworkParser {
  def parse(fileName: String): BooleanNetwork = {
    val src = scala.io.Source.fromFile(fileName)
    val empty = """\s*""".r

    for (line <- src.getLines()) {
      val lineTrimmed = line.trim();
      if (!lineTrimmed.startsWith("#") && !lineTrimmed.matches("""targets,\s*factors""") && lineTrimmed.nonEmpty) {
        val result = parseAll(transitionDef, lineTrimmed).toString
        if (!result.contains("parsed"))
          println(s"ERR: $result")
      }
    }

    BooleanNetwork(vars.toSeq, transitions)
  }

  def orDef: Parser[Expression] =
    andDef ~ rep("|" ~> andDef) ^^ {
      case l ~ ls => {
        if (ls.isEmpty)
          l
        else
          Or(l +: ls)
      }
    }

  def andDef: Parser[Expression] =
    negDef ~ rep("&" ~> negDef) ^^ {
      case l ~ ls => {
        if (ls.isEmpty)
          l
        else
          And(l +: ls)
      }
    }

  def negDef: Parser[Expression] =
    opt("!") ~ conjunctDef ^^ {
      case Some("!") ~ f => Neg(f)
      case Some(_) ~ _   => throw new IllegalArgumentException("Invalid input")
      case None ~ f      => f
    }

  def conjunctDef: Parser[Expression] =
    literalDef | "(" ~> orDef <~ ")"

  def literalDef: Parser[Literal] =
    "!" ~> varDef ^^ { case v => Literal(v, false) } | varDef ^^ { case v => Literal(v, true) }

  def varDef: Parser[String] = {
    val f: (String => String) = v => {
      v match {
        case "0" => throw new UnsupportedOperationException("0 is currently not supported")
        case "1" => throw new UnsupportedOperationException("1 is currently not supported")
        case _ => {
          vars += v
          v
        }
      }
    }

    ("(" ~> symbols) <~ ")" ^^ f | symbols ^^ f
  }

  def transitionDef: Parser[Transition] =
    (varDef <~ ",") ~ orDef ^^ {
      case v ~ x => {
        val t = Transition(v, x)
        transitions :+= t
        t
      }
    }
}
