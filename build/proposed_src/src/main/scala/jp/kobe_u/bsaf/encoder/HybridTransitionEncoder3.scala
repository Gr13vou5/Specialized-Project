package jp.kobe_u.bsaf.encoder

import jp.kobe_u.bsaf.bn.Transition
import jp.kobe_u.bsaf.util._
import org.sbml.jsbml.ext.qual.{Transition => QTransition}

import scala.collection.JavaConverters._

// Hybrid translation
object HybridTransitionEncoder3 extends TransitionEncoder {
  // Algorithm 2: HybridTranslation (for SBML)
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
      val output = outputs.head.getQualitativeSpecies() // v_i
      val inputs = qt.getListOfInputs().asScala.map(_.getQualitativeSpecies())

      val normalTerm = normalTerms.head
      val defaultTerm = defaultTerms.head

      var nodeNormal = normalTerm.getMath() // f_i
      var nodeDefault = ASTNodeFactory.not(nodeNormal)
      if (inputs.contains(output)) {
        val eqNode = ASTNodeFactory.nameAssigned(output, normalTerm.getResultLevel())
        val neqNode = ASTNodeFactory.not(eqNode)

        nodeNormal = ASTNodeFactory.and(neqNode, nodeNormal)
        nodeDefault = ASTNodeFactory.and(eqNode, nodeDefault)
      }

      val (satProblemPiNormal, varMapNormal) =
        SatProblem.fromExpressionToPIProblem(Expression.fromASTNode(nodeNormal).toNNF)
      val condsNormal = enumCondsWithLimit(satProblemPiNormal, varMapNormal, output) // M+
      val condsDefault =
        if (condsNormal.isEmpty)
          None
        else {
          val (satProblemPiDefault, varMapDefault) =
            SatProblem.fromExpressionToPIProblem(Expression.fromASTNode(nodeDefault).toNNF)
          enumCondsWithLimit(satProblemPiDefault, varMapDefault, output) // M-
        }

      println()
      println(condsNormal)
      println(condsDefault)

      if (condsNormal.isEmpty || condsDefault.isEmpty) { // if !(isOK+ & isOK-)
        println(s"\n# Use TseitinTransitionEncoder")
        TseitinTransitionEncoder.encodeQTransition(qt, attractorProblem, attractorVarMap)
      } else {
        for ((ft, conds) <- Seq((normalTerm, condsNormal), (defaultTerm, condsDefault))) {
          val resultLevel = ft.getResultLevel()
          assert(resultLevel == 0 || resultLevel == 1)

          // Convert each implicant into CNF
          conds.get.foreach(c => {
            val codes =
              c.map(lit => attractorVarMap(lit.name) * (if (lit.isPositive) -1 else 1)) // Negation of the implicant
            val outputCode = attractorVarMap(output)
            val outputLit = outputCode * (if (resultLevel == 1) 1 else -1)
            attractorProblem.addClause(codes + outputLit)

            println(c, codes)
          })
        }
      }
    }
  }

  // Algorithm 2: HybridTranslation (for BNET, etc.)
  def encodeTransition(t: Transition, attractorProblem: SatProblem, attractorVarMap: Map[String, Int]): Unit = {
    var x01 = t.f // f_i
    var x10: Expression = Neg(x01)

    val inputs = x01.getVars()
    if (inputs.contains(t.v)) {
      val lit = Literal(t.v, true)

      x01 = And(~lit, x01) // !v_i & f_i
      x10 = And(lit, x10) // v_i & !f_i
    }

    val (satProblemPi01, varMap01) = SatProblem.fromExpressionToPIProblem(x01.toNNF)
    val conds01 = enumCondsWithLimit(satProblemPi01, varMap01, t.v) // M+
    val (satProblemPi10, varMap10) = SatProblem.fromExpressionToPIProblem(x10.toNNF)
    val conds10 =
      if (conds01.isEmpty)
        None
      else
        enumCondsWithLimit(satProblemPi10, varMap10, t.v) // M-

    println()
    println(conds01)
    println(conds10)

    if (conds01.isEmpty || conds10.isEmpty) { // if !(isOK+ & isOK-)
      println(s"\n# Use TseitinTransitionEncoder")
      TseitinTransitionEncoder.encodeTransition(t, attractorProblem, attractorVarMap)
    } else {
      for ((is01, conds) <- Seq((true, conds01), (false, conds10))) {
        // Convert each implicant into CNF
        conds.get.foreach(c => {
          val codes =
            c.map(lit => attractorVarMap(lit.name) * (if (lit.isPositive) -1 else 1)) // Negation of the implicant
          val outputCode = attractorVarMap(t.v)
          val outputLit = outputCode * (if (is01) 1 else -1)
          attractorProblem.addClause(codes + outputLit)

          println(c, codes)
        })
      }
    }
  }
}
