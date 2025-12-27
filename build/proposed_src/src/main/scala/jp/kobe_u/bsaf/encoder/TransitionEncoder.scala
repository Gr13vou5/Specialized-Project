package jp.kobe_u.bsaf.encoder

import jp.kobe_u.bsaf.bn.Transition
import jp.kobe_u.bsaf.util.Literal
import jp.kobe_u.bsaf.util.SatProblem
import org.sat4j.core.VecInt
import org.sat4j.minisat.SolverFactory
import org.sat4j.specs.IVecInt
import org.sat4j.tools.ModelIterator
import org.sat4j.tools.SearchEnumeratorListener
import org.sat4j.tools.SolutionFoundListener
import org.sbml.jsbml.ext.qual.{Transition => QTransition}

import scala.collection.immutable.IndexedSeq

abstract class TransitionEncoder {
  protected[this] type Cond = Set[Literal]

  protected[this] def enumConds(problem: SatProblem, varMap: Map[String, Int], output: String = ""): Seq[Cond] = {
    var conds = IndexedSeq.empty[Cond]

    val solver = SolverFactory.newDefault()
    val sfl = new SolutionFoundListener() {
      override def onSolutionFound(solution: Array[Int]): Unit = {
        var cond = modelToCond(solution, varMap)
        if (cond.nonEmpty) {
          if (cond.size > 1 && output.nonEmpty) {
            cond = cond.filterNot(_.name == output)
          }

          println(cond)

          if (!conds.exists(c => isSubsumed(cond, c))) {
            conds = conds.filterNot(c => isSubsumed(c, cond)) :+ cond
          }
        }
      }

      override def onSolutionFound(solution: IVecInt): Unit = ???

      override def onUnsatTermination(): Unit = {
        println("UNSAT (DONE)")
      }
    }
    val enumerator = new SearchEnumeratorListener(sfl)
    solver.setSearchListener(enumerator)
    solver.newVar(problem.numVariables)
    problem.clauses.foreach(cl => solver.addClause(new VecInt(cl.toArray)))
    solver.isSatisfiable()

    conds
  }

  // Algorithm 1: PModelEnum (not exactly the same)
  // Here, the problem is already a PI problem
  protected[this] def enumCondsWithLimit(
      problem: SatProblem,
      varMap: Map[String, Int],
      output: String = ""
  ): Option[Seq[Cond]] = {
    var conds = IndexedSeq.empty[Cond]

    val maxNumModels = 1000 // cutoff
    val solver = new ModelIterator(SolverFactory.newDefault(), maxNumModels + 1) // ModelEnumerator
    solver.newVar(problem.numVariables)
    problem.clauses.foreach(cl => solver.addClause(new VecInt(cl.toArray)))

    var i = 0
    while (solver.isSatisfiable()) {
      i += 1

      var cond = modelToCond(solver.model(), varMap)
      if (cond.nonEmpty) {
        if (cond.size > 1 && output.nonEmpty) {
          cond = cond.filterNot(_.name == output)
        }

        if (!conds.exists(c => isSubsumed(cond, c))) {
          conds = conds.filterNot(c => isSubsumed(c, cond)) :+ cond
        }
      }
    }

    if (i > maxNumModels) None else Some(conds)
  }

  // Decode a model and obtain an implicant
  protected[this] def modelToCond(model: Array[Int], varMap: Map[String, Int]): Cond = {
    var cond = Set.empty[Literal]
    for ((v, i) <- varMap) {
      assert(model.contains(-i) || model.contains(-i - 1))

      if (model.contains(i)) {
        cond += Literal(v, true)
      } else if (model.contains(i + 1)) {
        cond += Literal(v, false)
      }
    }
    cond
  }

  protected[this] def isSubsumed(a: Cond, b: Cond): Boolean = {
    b.subsetOf(a) // a is subsumed by b
  }

  def encodeQTransition(qt: QTransition, attractorProblem: SatProblem, attractorVarMap: Map[String, Int]): Unit

  def encodeTransition(t: Transition, attractorProblem: SatProblem, attractorVarMap: Map[String, Int]): Unit
}
