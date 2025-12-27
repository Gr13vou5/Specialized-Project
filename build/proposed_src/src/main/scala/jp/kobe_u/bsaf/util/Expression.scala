package jp.kobe_u.bsaf.util

import org.sbml.jsbml.ASTNode
import org.sbml.jsbml.ASTNode.Type.LOGICAL_AND
import org.sbml.jsbml.ASTNode.Type.LOGICAL_NOT
import org.sbml.jsbml.ASTNode.Type.LOGICAL_OR
import org.sbml.jsbml.ASTNode.Type.RELATIONAL_EQ

import scala.collection.JavaConverters._

sealed abstract class Expression {
  def toNNF: Expression
  def getVars(): Set[String]
}

object Expression {
  def fromASTNode(node: ASTNode): Expression = {
    node.getType() match {
      case LOGICAL_OR => Or(node.getChildren().asScala.map(Expression.fromASTNode))

      case LOGICAL_AND => And(node.getChildren().asScala.map(Expression.fromASTNode))

      case LOGICAL_NOT => {
        assert(node.getChildCount() == 1)
        Neg(Expression.fromASTNode(node.getChild(0)))
      }

      case RELATIONAL_EQ => {
        assert(node.getChildCount() == 2)
        val children = node.getChildren().asScala
        val nameNode = children.find(_.isName())
        val intNode = children.find(_.isInteger())
        assert(nameNode.nonEmpty && intNode.nonEmpty)
        val v = intNode.get.getInteger()
        assert(v == 0 || v == 1)
        Literal(nameNode.get.getName(), v == 1)
      }

      case _ => throw new UnsupportedOperationException
    }
  }
}

case class Literal(name: String, isPositive: Boolean) extends Expression {
  def unary_~ = Literal(name, !isPositive)

  def toNNF: Expression = this

  def getVars(): Set[String] = Set(name)

  override def toString = if (isPositive) name else s"!$name"
}

case class Neg(x: Expression) extends Expression {
  def toNNF: Expression = x match {
    case Literal(name, isPositive) => Literal(name, !isPositive)
    case Neg(x)                    => x.toNNF
    case And(xs)                   => Or(xs.map(Neg)).toNNF
    case Or(xs)                    => And(xs.map(Neg)).toNNF
  }

  def getVars(): Set[String] = x.getVars()

  override def toString = s"Neg($x)"
}

case class And(xs: Set[Expression]) extends Expression {
  def toNNF: Expression = And(xs.map(_.toNNF)).simplified

  def simplified: Expression = {
    val a = simplifiedAnd
    if (a.xs.size == 1) a.xs.head else a
  }

  def simplifiedAnd: And = And(
    xs.flatMap {
      case a: And => a.simplifiedAnd.xs
      case x      => Seq(x)
    }
  )

  def getVars(): Set[String] = xs.flatMap(_.getVars())

  override def toString = xs.mkString("And(", ", ", ")")
}

object And {
  def apply(xs: Iterable[Expression]): And = And(xs.toSet)
  def apply(xs: Expression*): And = And(xs)
}

case class Or(xs: Set[Expression]) extends Expression {
  def toNNF: Expression = Or(xs.map(_.toNNF)).simplified

  def simplified: Expression = {
    val o = simplifiedOr
    if (o.xs.size == 1) o.xs.head else o
  }

  def simplifiedOr: Or = Or(xs.flatMap {
    case o: Or => o.simplifiedOr.xs
    case x     => Seq(x)
  })

  def getVars(): Set[String] = xs.flatMap(_.getVars())

  override def toString = xs.mkString("Or(", ", ", ")")
}

object Or {
  def apply(xs: Iterable[Expression]): Or = Or(xs.toSet)
  def apply(xs: Expression*): Or = Or(xs)
}
