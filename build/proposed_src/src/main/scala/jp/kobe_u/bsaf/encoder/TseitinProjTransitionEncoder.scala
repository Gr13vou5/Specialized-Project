package jp.kobe_u.bsaf.encoder

import jp.kobe_u.bsaf.bn.Transition
import jp.kobe_u.bsaf.util._
import org.sbml.jsbml.ext.qual.{Transition => QTransition}

import scala.collection.JavaConverters._

// Obsolete
object TseitinProjTransitionEncoder extends TransitionEncoder {
  def encodeQTransition(
      qt: QTransition,
      attractorProblem: SatProblem,
      attractorVarMap: Map[String, Int]
  ): Unit = {
    val (defaultTerms, normalTerms) = qt.getListOfFunctionTerms().asScala.partition(_.isDefaultTerm())
    assert(normalTerms.size <= 1)

    if (normalTerms.nonEmpty) {
      assert(defaultTerms.size == 1)

      val outputs = qt.getListOfOutputs().asScala
      assert(outputs.size == 1)
      val output = outputs.head.getQualitativeSpecies()

      val normalTerm = normalTerms.head
      val defaultTerm = defaultTerms.head

      val eqNode = ASTNodeFactory.nameAssigned(output, normalTerm.getResultLevel())
      val neqNode = ASTNodeFactory.not(eqNode)
      val nn = normalTerm.getMath()
      val nodeNormal = ASTNodeFactory.and(neqNode, nn)
      val nodeDefault = ASTNodeFactory.and(eqNode, ASTNodeFactory.not(nn))

      for (node <- Seq(nodeNormal, nodeDefault)) {
        val x = Expression.fromASTNode(ASTNodeFactory.not(node))

        println("\n# Formula")
        println(x)

        SatProblem.fromExpressionTseitin(x, false, attractorProblem, attractorVarMap)
      }
    }
  }

  def encodeTransition(t: Transition, attractorProblem: SatProblem, attractorVarMap: Map[String, Int]): Unit = {
    val lit = Literal(t.v, true)
    val x01 = And(~lit, t.f)
    val x10 = And(lit, Neg(t.f))

    for (x <- Seq(x01, x10)) {
      println("\n# Formula")
      println(x)

      SatProblem.fromExpressionTseitin(Neg(x), false, attractorProblem, attractorVarMap)
    }
  }
}
