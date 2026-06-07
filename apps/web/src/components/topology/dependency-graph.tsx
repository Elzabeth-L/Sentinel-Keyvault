"use client";

import {
  Background,
  Controls,
  Edge,
  MiniMap,
  Node,
  ReactFlow
} from "@xyflow/react";
import { useMemo } from "react";

type Graph = {
  root_resource_id: string;
  truncated: boolean;
  nodes: {
    id: string;
    label: string;
    resource_type: string;
    resource_group: string;
  }[];
  edges: {
    id: string;
    source: string;
    target: string;
    relationship_type: string;
  }[];
};

export function DependencyGraph({ graph }: { graph: Graph }) {
  const nodes = useMemo<Node[]>(
    () =>
      graph.nodes.map((node, index) => ({
        id: node.id,
        position: { x: (index % 8) * 240, y: Math.floor(index / 8) * 140 },
        data: {
          label: (
            <div className="min-w-40">
              <div className="font-semibold">{node.label}</div>
              <div className="mt-1 max-w-48 truncate text-[10px] text-slate-400">
                {node.resource_type}
              </div>
            </div>
          )
        },
        style: {
          color: "#edf6ff",
          background: node.id === graph.root_resource_id ? "#123d5a" : "#0d1b2e",
          border: `1px solid ${node.id === graph.root_resource_id ? "#32b5ff" : "#315170"}`,
          borderRadius: 12,
          padding: 12
        }
      })),
    [graph]
  );
  const edges = useMemo<Edge[]>(
    () =>
      graph.edges.map((edge) => ({
        id: edge.id,
        source: edge.source,
        target: edge.target,
        label: edge.relationship_type,
        animated: false,
        style: { stroke: "#4f83aa" },
        labelStyle: { fill: "#8fa7c2", fontSize: 10 }
      })),
    [graph.edges]
  );
  return (
    <ReactFlow
      nodes={nodes}
      edges={edges}
      fitView
      onlyRenderVisibleElements
      minZoom={0.05}
      maxZoom={2}
      nodesDraggable
    >
      <Background color="#203652" gap={24} />
      <MiniMap pannable zoomable nodeColor="#32b5ff" maskColor="rgba(7,17,31,.78)" />
      <Controls />
    </ReactFlow>
  );
}

