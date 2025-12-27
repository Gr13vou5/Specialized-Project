package jp.kobe_u.bsaf.bn

import jp.kobe_u.bsaf.sbml.SbmlQualModel
import jp.kobe_u.bsaf.util._

import scala.collection.JavaConverters._
import scala.collection.immutable.IndexedSeq

case class Transition(v: String, f: Expression)

case class BooleanNetwork(vars: Seq[String], transitions: Seq[Transition]) {
  def show(): Unit = {
    println(s"Variables: ${vars.mkString(", ")}")
    println("Transitions:")
    transitions.foreach(println)
  }
}

object BooleanNetwork {
  def fromBnetFile(fileName: String): BooleanNetwork = BnetParser.parse(fileName)

  def fromSbmlQualModel(sqm: SbmlQualModel): BooleanNetwork = {
    var vars = IndexedSeq.empty[String]

    for (qs <- sqm.qualitativeSpecies) {
      val lb = if (qs.isSetInitialLevel()) qs.getInitialLevel() else 0
      if (!(lb == 0 && qs.isSetMaxLevel() && qs.getMaxLevel() == 1))
        throw new IllegalArgumentException("Variables must be Boolean")

      val v = qs.getId()
      vars :+= v
    }

    var transitions = IndexedSeq.empty[Transition]

    for (qt <- sqm.transitions) {
      val (defaultTerms, normalTerms) = qt.getListOfFunctionTerms().asScala.partition(_.isDefaultTerm())
      assert(normalTerms.size <= 1)

      if (normalTerms.nonEmpty) {
        assert(defaultTerms.size == 1)

        val outputs = qt.getListOfOutputs().asScala
        assert(outputs.size == 1)
        val output = outputs.head.getQualitativeSpecies()

        val normalTerm = normalTerms.head
        val resultLevel = normalTerm.getResultLevel()
        assert(resultLevel == 0 || resultLevel == 1)

        val x = Expression.fromASTNode(normalTerm.getMath())
        val f = if (resultLevel == 1) x else Neg(x)

        transitions :+= Transition(output, f)
      }
    }

    BooleanNetwork(vars.distinct, transitions)
  }
}
