// Pure layout helper (auto-arranges nodes via dagre). Not part of the
// data-access layer -- this is presentation concern only, used by
// components/memories/memory-graph.tsx.

import dagre from "dagre";

export interface LayoutNode {
  id: string;
}

export interface LayoutEdge {
  id: string;
  source: string;
  target: string;
}

export const NODE_WIDTH = 180;
export const NODE_HEIGHT = 56;

export function layoutGraph(
  nodes: LayoutNode[],
  edges: LayoutEdge[],
): Map<string, { x: number; y: number }> {
  const graph = new dagre.graphlib.Graph();
  graph.setGraph({ rankdir: "LR", nodesep: 40, ranksep: 90 });
  graph.setDefaultEdgeLabel(() => ({}));

  for (const node of nodes) {
    graph.setNode(node.id, { width: NODE_WIDTH, height: NODE_HEIGHT });
  }
  for (const edge of edges) {
    if (graph.hasNode(edge.source) && graph.hasNode(edge.target)) {
      graph.setEdge(edge.source, edge.target);
    }
  }

  dagre.layout(graph);

  const positions = new Map<string, { x: number; y: number }>();
  for (const node of nodes) {
    const { x, y } = graph.node(node.id);
    positions.set(node.id, { x: x - NODE_WIDTH / 2, y: y - NODE_HEIGHT / 2 });
  }
  return positions;
}
