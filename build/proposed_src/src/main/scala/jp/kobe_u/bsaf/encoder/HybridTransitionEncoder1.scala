package jp.kobe_u.bsaf.encoder

import jp.kobe_u.bsaf.bn.Transition
import jp.kobe_u.bsaf.util._
import org.sbml.jsbml.ext.qual.{Transition => QTransition}

import scala.collection.JavaConverters._

// Obsolete
object HybridTransitionEncoder1 extends TransitionEncoder {
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
      val nodeNormal = normalTerm.getMath()

      val x = Expression.fromASTNode(nodeNormal)
      val nnf = x.toNNF

      println("\n# Formula")
      println(x)
      println(nnf)

      val (satProblemPi, varMap) = SatProblem.fromExpressionToPIProblem(nnf)

      println("############################################################")
      println(varMap)
      println("------------------------------------------------------------")
      satProblemPi.showDIMACS()
      println("############################################################")

      val conds = enumConds(satProblemPi, varMap)

      val resultLevel = normalTerm.getResultLevel()
      assert(resultLevel == 0 || resultLevel == 1)

      val condsCodes = conds.map(c => c.map(lit => attractorVarMap(lit.name) * (if (lit.isPositive) 1 else -1)))
      val negCondsAuxVars = condsCodes.map(a => {
        val auxVar = attractorProblem.newCode()
        tseitinCls(a.toSeq.map(-_), auxVar).foreach(attractorProblem.addClause)
        auxVar
      })

      val outputCode = attractorVarMap(output)
      val outputLit = outputCode * (if (resultLevel == 1) 1 else -1)
      negCondsAuxVars.foreach(i => attractorProblem.addClause(Seq(i, outputLit)))
      attractorProblem.addClause((negCondsAuxVars :+ outputLit).map(-_))

      println(conds)
      println(condsCodes)
      println(negCondsAuxVars)
    }
  }

  def encodeTransition(t: Transition, attractorProblem: SatProblem, attractorVarMap: Map[String, Int]): Unit = {
    val x = t.f
    val nnf = x.toNNF

    println("\n# Formula")
    println(x)
    println(nnf)

    val (satProblemPi, varMap) = SatProblem.fromExpressionToPIProblem(nnf)

    println("############################################################")
    println(varMap)
    println("------------------------------------------------------------")
    satProblemPi.showDIMACS()
    println("############################################################")

    val conds = enumConds(satProblemPi, varMap)

    val condsCodes = conds.map(c => c.map(lit => attractorVarMap(lit.name) * (if (lit.isPositive) 1 else -1)))
    val negCondsAuxVars = condsCodes.map(a => {
      val auxVar = attractorProblem.newCode()
      tseitinCls(a.toSeq.map(-_), auxVar).foreach(attractorProblem.addClause)
      auxVar
    })

    val outputLit = attractorVarMap(t.v)
    negCondsAuxVars.foreach(i => attractorProblem.addClause(Seq(i, outputLit)))
    attractorProblem.addClause((negCondsAuxVars :+ outputLit).map(-_))

    println(conds)
    println(condsCodes)
    println(negCondsAuxVars)
  }

  private[this] def tseitinCls(cl: Seq[Int], auxVar: Int): Seq[Seq[Int]] = {
    val cl0 = -auxVar +: cl
    val cls = for (i <- cl) yield Seq(-i, auxVar)
    cl0 +: cls
  }
}
