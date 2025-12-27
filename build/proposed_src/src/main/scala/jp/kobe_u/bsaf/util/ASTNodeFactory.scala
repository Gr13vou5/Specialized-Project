package jp.kobe_u.bsaf.util

import org.sbml.jsbml.ASTNode
import org.sbml.jsbml.ASTNode.Type.LOGICAL_AND
import org.sbml.jsbml.ASTNode.Type.LOGICAL_NOT
import org.sbml.jsbml.ASTNode.Type.LOGICAL_OR
import org.sbml.jsbml.ASTNode.Type.NAME
import org.sbml.jsbml.ASTNode.Type.RELATIONAL_EQ

object ASTNodeFactory {
  def name(s: String): ASTNode = {
    val node = new ASTNode(NAME)
    node.setName(s)
    node
  }

  def int(n: Int): ASTNode = new ASTNode(n)

  def eq(node0: ASTNode, node1: ASTNode): ASTNode = {
    val node = new ASTNode(RELATIONAL_EQ)
    node.addChild(node0)
    node.addChild(node1)
    node
  }

  def nameAssigned(s: String, n: Int): ASTNode = eq(name(s), int(n))

  def not(node0: ASTNode): ASTNode = {
    val node = new ASTNode(LOGICAL_NOT)
    node.addChild(node0)
    node
  }

  def and(nodes: Iterable[ASTNode]): ASTNode = {
    val node = new ASTNode(LOGICAL_AND)
    nodes.foreach(node.addChild)
    node
  }
  def and(nodes: ASTNode*): ASTNode = and(nodes)

  def or(nodes: Iterable[ASTNode]): ASTNode = {
    val node = new ASTNode(LOGICAL_OR)
    nodes.foreach(node.addChild)
    node
  }
  def or(nodes: ASTNode*): ASTNode = or(nodes)
}
