import '@xyflow/react/dist/style.css'
import { useEffect, useMemo } from 'react'
import { Background, Controls, MiniMap, ReactFlow, ReactFlowProvider, useReactFlow } from '@xyflow/react'
import { resultNodeTypes } from '../graph/resultNodeTypes'
import { STATE_COLORS } from '../graph/style'
import { buildGraph, type ResultFlowNode } from '../results/graphData'
import type { NodeResult, Snapshot, Trace } from '../types'

interface Props {
  snapshot: Snapshot
  results: NodeResult[]
  trace: Trace | undefined
  selected: number | null
  focusAffected: boolean
  /** Changes whenever the page wants the graph to zoom to the selected node (e.g. a table click). */
  focusNonce: number
  onSelect: (id: number | null) => void
}

export default function ResultGraph(props: Props) {
  return (
    <ReactFlowProvider>
      <Inner {...props} />
    </ReactFlowProvider>
  )
}

function Inner({ snapshot, results, trace, selected, focusAffected, focusNonce, onSelect }: Props) {
  const rf = useReactFlow()
  const graph = useMemo(
    () => buildGraph(snapshot, results, { selected, trace, focusAffected }),
    [snapshot, results, selected, trace, focusAffected],
  )

  useEffect(() => {
    if (focusNonce > 0 && selected !== null) {
      rf.fitView({ nodes: [{ id: String(selected) }], duration: 400, padding: 1.2, maxZoom: 1.1 })
    }
    // only a new nonce should move the camera, not every selection change
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [focusNonce])

  return (
    <ReactFlow
      nodes={graph.nodes}
      edges={graph.edges}
      nodeTypes={resultNodeTypes}
      nodesDraggable={false}
      nodesConnectable={false}
      elementsSelectable={false}
      colorMode="dark"
      minZoom={0.1}
      fitView
      onNodeClick={(_, n) => onSelect(Number(n.id))}
      onPaneClick={() => onSelect(null)}
    >
      <Background gap={24} color="#243049" />
      <Controls showInteractive={false} />
      <MiniMap pannable zoomable maskColor="rgba(11,16,32,0.7)" style={{ background: '#111827' }}
        nodeColor={(n) => STATE_COLORS[(n as ResultFlowNode).data.result.state]} />
    </ReactFlow>
  )
}