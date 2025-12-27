package jp.kobe_u.bsaf.util

import org.sat4j.core.VecInt
import org.sat4j.minisat.SolverFactory
import org.sat4j.tools.ModelIterator

import java.io.PrintWriter
import scala.collection.immutable.IndexedSeq
import scala.math.abs

case class SatProblem(
    var numVariables: Int = 0,
    var numClauses: Int = 0,
    var clauses: IndexedSeq[Seq[Int]] = IndexedSeq.empty
) {
  def init(): Unit = {
    numVariables = 0
    numClauses = 0
    clauses = IndexedSeq.empty
  }

  def newCode(): Int = {
    numVariables += 1
    assert(numVariables < Int.MaxValue)
    numVariables
  }

  def newCodes(n: Int): Int = {
    if (n <= 0) {
      0
    } else {
      val codeStart = numVariables + 1
      numVariables += n
      assert(numVariables < Int.MaxValue)
      codeStart
    }
  }

  def addClause(cl: Seq[Int]): Unit = {
    clauses :+= cl
    numClauses += 1
  }

  def addClause(cl: Iterable[Int]): Unit = {
    addClause(cl.toSeq)
  }

  def getDIMACSLines(): Iterator[String] = {
    val h = Seq(s"p cnf $numVariables $numClauses").iterator
    h ++ clauses.iterator.map(_.mkString(" ") + " 0")
  }

  def showDIMACS(): Unit = getDIMACSLines().foreach(println)

  def dump(cnfFileName: String): Unit = {
    val out = new PrintWriter(cnfFileName)
    getDIMACSLines().foreach(out.println)
    out.close()
  }

  def dumpProj(cnfFileName: String, vars: Seq[Int]): Unit = {
    require(vars.forall(v => 0 < v && v <= numVariables))

    val out = new PrintWriter(cnfFileName)
    out.println(s"c p show ${vars.distinct.mkString(" ")} 0")
    getDIMACSLines().foreach(out.println)
    out.close()
  }

  def toPIProblem: SatProblem = {
    val numRelevantVars = numVariables * 2
    val problemPi = SatProblem(numRelevantVars)

    for (cl <- clauses) {
      val newCl = cl.map(i => if (i < 0) abs(i) * 2 else i * 2 - 1)
      problemPi.addClause(newCl)
    }

    for (i <- 1 until numRelevantVars by 2) {
      problemPi.addClause(Seq(-i, -i - 1))
    }

    problemPi.addPIConstraint()

    problemPi
  }

  // Jabbour et al. 2014
  private def addPIConstraint(targetVars: Seq[Int] = 1 to numVariables): Unit = {
    require(1 <= targetVars.min && targetVars.max <= numVariables)

    val relevantCls = clauses
    for (i <- targetVars.distinct) {
      val cls = relevantCls.withFilter(_.contains(i)).map(_.filterNot(_ == i))
      if (cls.isEmpty) {
        addClause(Seq(-i))
      } else if (!cls.exists(_.isEmpty)) {
        val cl = cls.map {
          case Seq(head) => head
          case x => {
            val auxVar = newCode()
            SatProblem.tseitinCls(x, auxVar).foreach(addClause)
            auxVar
          }
        }
        addClause(-i +: cl.map(-_))
      }
    }
  }
}

object SatProblem {
  private[this] var problem = SatProblem()
  private[this] var varMap = Map.empty[String, Int]
  private[this] var cacheMap = Map.empty[Expression, Int]
  private[this] var auxVars = Set.empty[Int]

  def fromExpression(x: Expression): (SatProblem, Map[String, Int]) = {
    val (problemPi, varMapPi) = SatProblem.fromExpressionToPIProblem(Neg(x))

    val solver = new ModelIterator(SolverFactory.newDefault())
    solver.newVar(problemPi.numVariables)
    problemPi.clauses.foreach(cl => solver.addClause(new VecInt(cl.toArray)))

    problem = SatProblem()
    varMap = varMapPi.keys.zip(1 to varMapPi.size).toMap
    problem.newCodes(varMap.size)
    while (solver.isSatisfiable()) {
      val model = solver.model()
      var cl = Set.empty[Int]

      for ((v, i) <- varMapPi) {
        assert(model.contains(-i) || model.contains(-i - 1))

        if (model.contains(i))
          cl += -varMap(v)
        else if (model.contains(i + 1))
          cl += varMap(v)
      }

      assert(cl.nonEmpty)
      problem.addClause(cl)
    }

    (problem, varMap)
  }

  def fromExpressionTseitin(
      x: Expression,
      equivTseitin: Boolean,
      currentProblem: SatProblem = SatProblem(),
      currentVarMap: Map[String, Int] = Map.empty
  ): (SatProblem, Map[String, Int]) = {
    val (lit, p, m) = fromExpressionTseitinLit(x, equivTseitin, currentProblem, currentVarMap)
    p.addClause(Seq(lit))

    (p, m)
  }

  def fromExpressionTseitinLit(
      x: Expression,
      equivTseitin: Boolean,
      currentProblem: SatProblem = SatProblem(),
      currentVarMap: Map[String, Int] = Map.empty
  ): (Int, SatProblem, Map[String, Int]) = {
    problem = currentProblem
    varMap = currentVarMap

    val lit = tseitin(if (equivTseitin) x else x.toNNF, equivTseitin)

    (lit, problem, varMap)
  }

  def fromExpressionTseitinCached(
      x: Expression,
      equivTseitin: Boolean,
      currentProblem: SatProblem = SatProblem(),
      currentVarMap: Map[String, Int] = Map.empty,
      currentCacheMap: Map[Expression, Int] = Map.empty
  ): (SatProblem, Map[String, Int], Map[Expression, Int]) = {
    val (lit, p, vm, cm) =
      fromExpressionTseitinCachedLit(x, equivTseitin, currentProblem, currentVarMap, currentCacheMap)
    p.addClause(Seq(lit))

    (p, vm, cm)
  }

  def fromExpressionTseitinCachedLit(
      x: Expression,
      equivTseitin: Boolean,
      currentProblem: SatProblem = SatProblem(),
      currentVarMap: Map[String, Int] = Map.empty,
      currentCacheMap: Map[Expression, Int] = Map.empty
  ): (Int, SatProblem, Map[String, Int], Map[Expression, Int]) = {
    problem = currentProblem
    varMap = currentVarMap
    cacheMap = currentCacheMap

    val lit = tseitinCached(if (equivTseitin) x else x.toNNF, equivTseitin)

    (lit, problem, varMap, cacheMap)
  }

  private[this] def tseitin(x: Expression, equiv: Boolean): Int = {
    x match {
      case Neg(x) => -tseitin(x, equiv)

      case Literal(name, isPositive) => {
        val c = varMap.getOrElse(name, problem.newCode())
        varMap += name -> c
        if (isPositive) c else -c
      }

      case And(xs) => {
        val lits = xs.map(tseitin(_, equiv))
        val c = problem.newCode()
        lits.foreach(lit => problem.addClause(Seq(-c, lit)))
        if (equiv) {
          problem.addClause(lits.map(-_) + c)
        }
        c
      }

      case Or(xs) => {
        val lits = xs.map(tseitin(_, equiv))
        val c = problem.newCode()
        problem.addClause(lits + -c)
        if (equiv) {
          lits.foreach(lit => problem.addClause(Seq(-lit, c)))
        }
        c
      }
    }
  }

  private[this] def tseitinCached(x: Expression, equiv: Boolean): Int = {
    x match {
      case Neg(x) => -tseitinCached(x, equiv)

      case lit: Literal => tseitin(lit, equiv)

      case and: And => {
        if (cacheMap.contains(and)) {
          cacheMap(and)
        } else {
          val lits = and.xs.map(tseitinCached(_, equiv))
          val c = problem.newCode()
          lits.foreach(lit => problem.addClause(Seq(-c, lit)))
          if (equiv) {
            problem.addClause(lits.map(-_) + c)
          }
          cacheMap += and -> c
          c
        }
      }

      case or: Or => {
        if (cacheMap.contains(or)) {
          cacheMap(or)
        } else {
          val lits = or.xs.map(tseitinCached(_, equiv))
          val c = problem.newCode()
          problem.addClause(lits + -c)
          if (equiv) {
            lits.foreach(lit => problem.addClause(Seq(-lit, c)))
          }
          cacheMap += or -> c
          c
        }
      }
    }
  }

  def fromExpressionToPIProblem(x: Expression): (SatProblem, Map[String, Int]) = {
    problem = SatProblem()
    varMap = Map.empty
    auxVars = Set.empty

    problem.addClause(Seq(tseitinPI(x.toNNF)))
    problem.addPIConstraint()

    (problem, varMap)
  }

  private[this] def tseitinPI(x: Expression): Int = {
    x match {
      case Literal(name, isPositive) => {
        // Jabbour et al. 2014
        if (!varMap.contains(name)) {
          val c0 = problem.newCodes(2)
          varMap += name -> c0
          problem.addClause(Seq(-c0, -c0 - 1))
        }
        val c = varMap(name)
        if (isPositive) c else c + 1
      }

      case And(xs) => {
        val lits = xs.map(tseitinPI)
        val c = problem.newCode()
        auxVars += c
        lits.foreach(lit => problem.addClause(Seq(-c, lit)))
        c
      }

      case Or(xs) => {
        val lits = xs.map(tseitinPI)
        val c = problem.newCode()
        auxVars += c
        problem.addClause(lits + -c)
        c
      }

      case _ => throw new UnsupportedOperationException
    }
  }

  private def tseitinCls(cl: Seq[Int], auxVar: Int): Seq[Seq[Int]] = {
    val cl0 = -auxVar +: cl
    val cls = for (i <- cl) yield Seq(-i, auxVar)
    cl0 +: cls
  }
}
