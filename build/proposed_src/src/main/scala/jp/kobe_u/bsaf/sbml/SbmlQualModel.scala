package jp.kobe_u.bsaf.sbml

import org.sbml.jsbml.SBMLReader
import org.sbml.jsbml.ext.qual.QualConstants
import org.sbml.jsbml.ext.qual.QualModelPlugin
import org.sbml.jsbml.ext.qual.QualitativeSpecies
import org.sbml.jsbml.ext.qual.{Transition => QTransition}

import scala.collection.JavaConverters._

case class SbmlQualModel(qualitativeSpecies: Seq[QualitativeSpecies], transitions: Seq[QTransition])

object SbmlQualModel {
  def fromFile(fileName: String): SbmlQualModel = {
    val sdoc = new SBMLReader().readSBMLFromFile(fileName)
    val smodel = sdoc.getModel()
    val plugin = smodel.getExtension(QualConstants.namespaceURI)
    val qualModel = plugin match {
      case q: QualModelPlugin => q
      case _                  => throw new Exception("Failed creating the qual model plugin")
    }

    val qss = qualModel.getListOfQualitativeSpecies().asScala
    val qts = qualModel.getListOfTransitions().asScala

    SbmlQualModel(qss, qts)
  }
}
