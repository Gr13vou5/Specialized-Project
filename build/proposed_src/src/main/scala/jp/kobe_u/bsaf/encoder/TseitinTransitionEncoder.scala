package jp.kobe_u.bsaf.encoder

import jp.kobe_u.bsaf.bn.Transition
import jp.kobe_u.bsaf.util._
import org.sbml.jsbml.ext.qual.{Transition => QTransition}

import scala.collection.JavaConverters._

// Direct translation
object TseitinTransitionEncoder extends TransitionEncoder {
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

      val eqNode = ASTNodeFactory.nameAssigned(output, normalTerm.getResultLevel())

      val x = Expression.fromASTNode(normalTerm.getMath())
      val nnf = x.toNNF
      println("\n# Formula")
      println(x)
      println(nnf)

      val (xLit, _, _) = SatProblem.fromExpressionTseitinLit(nnf, true, attractorProblem, attractorVarMap)
      val (outputLit, _, _) =
        SatProblem.fromExpressionTseitinLit(Expression.fromASTNode(eqNode), true, attractorProblem, attractorVarMap)
      println(s"# Output lit: ${outputLit}, x lit: ${xLit}")

      attractorProblem.addClause(Seq(outputLit, -xLit))
      attractorProblem.addClause(Seq(-outputLit, xLit))
    }
  }

  def encodeTransition(t: Transition, attractorProblem: SatProblem, attractorVarMap: Map[String, Int]): Unit = {
    val x = t.f
    val nnf = x.toNNF
    println("\n# Formula")
    println(x)
    println(nnf)

    val (xLit, _, _) = SatProblem.fromExpressionTseitinLit(nnf, true, attractorProblem, attractorVarMap)
    val (outputLit, _, _) =
      SatProblem.fromExpressionTseitinLit(Literal(t.v, true), true, attractorProblem, attractorVarMap)
    println(s"# Output lit: ${outputLit}, x lit: ${xLit}")

    attractorProblem.addClause(Seq(outputLit, -xLit))
    attractorProblem.addClause(Seq(-outputLit, xLit))
  }
}
