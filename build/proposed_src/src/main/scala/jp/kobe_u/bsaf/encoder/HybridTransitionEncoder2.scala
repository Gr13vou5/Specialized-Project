package jp.kobe_u.bsaf.encoder

import jp.kobe_u.bsaf.bn.Transition
import jp.kobe_u.bsaf.util._
import org.sbml.jsbml.ext.qual.{Transition => QTransition}

import scala.collection.JavaConverters._

// Obsolete
object HybridTransitionEncoder2 extends TransitionEncoder {
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
      val inputs = qt.getListOfInputs().asScala.map(_.getQualitativeSpecies())

      val normalTerm = normalTerms.head
      val defaultTerm = defaultTerms.head

      var nodeNormal = normalTerm.getMath()
      var nodeDefault = ASTNodeFactory.not(nodeNormal)
      if (inputs.contains(output)) {
        val eqNode = ASTNodeFactory.nameAssigned(output, normalTerm.getResultLevel())
        val neqNode = ASTNodeFactory.not(eqNode)

        nodeNormal = ASTNodeFactory.and(neqNode, nodeNormal)
        nodeDefault = ASTNodeFactory.and(eqNode, nodeDefault)
      }

      val (satProblemPiNormal, varMapNormal) =
        SatProblem.fromExpressionToPIProblem(Expression.fromASTNode(nodeNormal).toNNF)
      val (satProblemPiDefault, varMapDefault) =
        SatProblem.fromExpressionToPIProblem(Expression.fromASTNode(nodeDefault).toNNF)

      val numVariablesThreshhold = 100
      if (
        satProblemPiNormal.numVariables >= numVariablesThreshhold || satProblemPiDefault.numVariables >= numVariablesThreshhold
      ) {
        println(s"\n# Use HybridTransitionEncoder1 (numVariables >= ${numVariablesThreshhold})")
        HybridTransitionEncoder1.encodeQTransition(qt, attractorProblem, attractorVarMap)
      } else {
        for (
          (ft, satProblemPi, varMap) <- Seq(
            (normalTerm, satProblemPiNormal, varMapNormal),
            (defaultTerm, satProblemPiDefault, varMapDefault)
          )
        ) {
          println("############################################################")
          println(varMap)
          println("------------------------------------------------------------")
          satProblemPi.showDIMACS()
          println("############################################################")

          val conds = enumConds(satProblemPi, varMap, output)

          val resultLevel = ft.getResultLevel()
          assert(resultLevel == 0 || resultLevel == 1)

          conds.foreach(c => {
            val codes = c.map(lit => attractorVarMap(lit.name) * (if (lit.isPositive) -1 else 1)) // negation of cond
            val outputCode = attractorVarMap(output)
            val outputLit = outputCode * (if (resultLevel == 1) 1 else -1)
            attractorProblem.addClause(codes + outputLit)

            println(c, codes)
          })
        }
      }
    }
  }

  def encodeTransition(t: Transition, attractorProblem: SatProblem, attractorVarMap: Map[String, Int]): Unit = {
    var x01 = t.f
    var x10: Expression = Neg(x01)

    val inputs = x01.getVars()
    if (inputs.contains(t.v)) {
      val lit = Literal(t.v, true)

      x01 = And(~lit, x01)
      x10 = And(lit, x10)
    }

    val (satProblemPi01, varMap01) = SatProblem.fromExpressionToPIProblem(x01.toNNF)
    val (satProblemPi10, varMap10) = SatProblem.fromExpressionToPIProblem(x10.toNNF)

    val numVariablesThreshhold = 100
    if (
      satProblemPi01.numVariables >= numVariablesThreshhold || satProblemPi10.numVariables >= numVariablesThreshhold
    ) {
      println(s"\n# Use HybridTransitionEncoder1 (numVariables >= ${numVariablesThreshhold})")
      HybridTransitionEncoder1.encodeTransition(t, attractorProblem, attractorVarMap)
    } else {
      for (
        (is01, satProblemPi, varMap) <- Seq(
          (true, satProblemPi01, varMap01),
          (false, satProblemPi10, varMap10)
        )
      ) {
        println("############################################################")
        println(varMap)
        println("------------------------------------------------------------")
        satProblemPi.showDIMACS()
        println("############################################################")

        val conds = enumConds(satProblemPi, varMap, t.v)

        conds.foreach(c => {
          val codes = c.map(lit => attractorVarMap(lit.name) * (if (lit.isPositive) -1 else 1)) // negation of cond
          val outputCode = attractorVarMap(t.v)
          val outputLit = outputCode * (if (is01) 1 else -1)
          attractorProblem.addClause(codes + outputLit)

          println(c, codes)
        })
      }
    }
  }
}
