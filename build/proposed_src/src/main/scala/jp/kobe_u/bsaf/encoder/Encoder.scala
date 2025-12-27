package jp.kobe_u.bsaf.encoder

import jp.kobe_u.bsaf.bn.BooleanNetwork
import jp.kobe_u.bsaf.sbml.SbmlQualModel
import jp.kobe_u.bsaf.util.SatProblem

abstract class Encoder(transitionEncoder: TransitionEncoder) {
  def encodeSbmlQualModel(sqm: SbmlQualModel): (SatProblem, Map[String, Int]) = {
    val attractorProblem = SatProblem()
    var attractorVarMap = Map.empty[String, Int]
    var vars = Set.empty[String]

    for (qs <- sqm.qualitativeSpecies) {
      val lb = if (qs.isSetInitialLevel()) qs.getInitialLevel() else 0
      if (!(lb == 0 && qs.isSetMaxLevel() && qs.getMaxLevel() == 1))
        throw new UnsupportedOperationException("Multivalued is currently not supported")

      val v = qs.getId()
      vars += v
      attractorVarMap += v -> attractorProblem.newCode()
    }

    sqm.transitions.foreach(transitionEncoder.encodeQTransition(_, attractorProblem, attractorVarMap))

    (attractorProblem, attractorVarMap)
  }

  def encodeBooleanNetwork(bn: BooleanNetwork): (SatProblem, Map[String, Int]) = {
    val attractorProblem = SatProblem()
    val attractorVarMap = Map(bn.vars.map(_ -> attractorProblem.newCode()): _*)

    bn.transitions.foreach(transitionEncoder.encodeTransition(_, attractorProblem, attractorVarMap))

    (attractorProblem, attractorVarMap)
  }
}

object TseitinEncoder extends Encoder(TseitinTransitionEncoder)
object TseitinProjEncoder extends Encoder(TseitinProjTransitionEncoder)
object PIEncoder extends Encoder(PITransitionEncoder)
object HybridEncoder1 extends Encoder(HybridTransitionEncoder1)
object HybridEncoder2 extends Encoder(HybridTransitionEncoder2)
object HybridEncoder3 extends Encoder(HybridTransitionEncoder3)
