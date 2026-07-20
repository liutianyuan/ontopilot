import React, { useEffect, useRef, useState } from 'react'
import { forceSimulation, forceLink, forceManyBody, forceCenter, forceCollide, Simulation, SimulationNodeDatum } from 'd3-force'
import { select } from 'd3-selection'
import { zoom as d3zoom, zoomIdentity, D3ZoomEvent, ZoomBehavior, ZoomTransform } from 'd3-zoom'
import { TraceEvent, OntologyDetail } from '../types'

const WIDTH = 800
const HEIGHT = 560
const MIN_SCALE = 0.4
const MAX_SCALE = 3

interface GraphNode extends SimulationNodeDatum {
  id: string
  description: string
  properties: { name: string; type: string; description: string }[]
}

interface GraphLink {
  source: string | GraphNode
  target: string | GraphNode
  label: string
}

interface Props {
  ontologyId: string
  traceEvents: TraceEvent[]
}

interface HoverInfo {
  node: GraphNode
  x: number
  y: number
}

export function OntologyGraphPanel({ ontologyId, traceEvents }: Props) {
  const [objectTypes, setObjectTypes] = useState<OntologyDetail['object_types']>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(false)
  const [nodes, setNodes] = useState<GraphNode[]>([])
  const [renderLinks, setRenderLinks] = useState<GraphLink[]>([])
  const [hover, setHover] = useState<HoverInfo | null>(null)
  const [transform, setTransform] = useState<ZoomTransform>(zoomIdentity)
  const svgRef = useRef<SVGSVGElement | null>(null)
  const zoomBehaviorRef = useRef<ZoomBehavior<SVGSVGElement, unknown> | null>(null)
  const simulationRef = useRef<Simulation<GraphNode, GraphLink> | null>(null)
  const draggingRef = useRef<GraphNode | null>(null)

  useEffect(() => {
    if (!ontologyId) return
    let ignore = false
    setLoading(true)
    setError(false)
    fetch(`/api/ontology/detail/${ontologyId}`)
      .then(res => {
        if (!res.ok) throw new Error('bad status')
        return res.json()
      })
      .then((data: OntologyDetail) => {
        if (!ignore) setObjectTypes(data.object_types || [])
      })
      .catch(() => {
        if (!ignore) setError(true)
      })
      .finally(() => {
        if (!ignore) setLoading(false)
      })
    return () => {
      ignore = true
    }
  }, [ontologyId])

  useEffect(() => {
    setHover(null)
    setTransform(zoomIdentity)
    if (svgRef.current && zoomBehaviorRef.current) {
      select(svgRef.current).call(zoomBehaviorRef.current.transform, zoomIdentity)
    }
    if (objectTypes.length === 0) {
      setNodes([])
      setRenderLinks([])
      simulationRef.current?.stop()
      return
    }
    const typeNames = new Set(objectTypes.map(t => t.name))
    const simNodes: GraphNode[] = objectTypes.map(t => ({
      id: t.name,
      description: t.description,
      properties: t.properties,
    }))
    const simLinks: GraphLink[] = []
    for (const t of objectTypes) {
      for (const link of t.links) {
        if (typeNames.has(link.target)) {
          simLinks.push({ source: t.name, target: link.target, label: link.name })
        }
      }
    }

    const sim = forceSimulation<GraphNode>(simNodes)
      .force('link', forceLink<GraphNode, GraphLink>(simLinks).id(d => d.id).distance(140))
      .force('charge', forceManyBody().strength(-320))
      .force('center', forceCenter(WIDTH / 2, HEIGHT / 2))
      .force('collide', forceCollide(46))
      .on('tick', () => {
        setNodes([...simNodes])
        setRenderLinks([...simLinks])
      })

    simulationRef.current = sim
    return () => {
      sim.stop()
    }
  }, [objectTypes])

  useEffect(() => {
    const svg = svgRef.current
    if (!svg) return
    const zoomBehavior = d3zoom<SVGSVGElement, unknown>()
      .scaleExtent([MIN_SCALE, MAX_SCALE])
      .filter((event: any) => {
        if (event.type === 'wheel') return true
        if (event.target?.closest?.('[data-graph-node]')) return false
        return !event.ctrlKey && !event.button
      })
      .on('zoom', (event: D3ZoomEvent<SVGSVGElement, unknown>) => setTransform(event.transform))
    zoomBehaviorRef.current = zoomBehavior
    select(svg).call(zoomBehavior)
    return () => {
      select(svg).on('.zoom', null)
    }
  }, [])

  const zoomBy = (factor: number) => {
    const svg = svgRef.current
    const zoomBehavior = zoomBehaviorRef.current
    if (!svg || !zoomBehavior) return
    select(svg).call(zoomBehavior.scaleBy, factor)
  }

  const resetZoom = () => {
    const svg = svgRef.current
    const zoomBehavior = zoomBehaviorRef.current
    if (!svg || !zoomBehavior) return
    select(svg).call(zoomBehavior.transform, zoomIdentity)
  }

  const toSvgPoint = (clientX: number, clientY: number) => {
    const svg = svgRef.current
    if (!svg) return { x: 0, y: 0 }
    const rect = svg.getBoundingClientRect()
    const viewBoxX = ((clientX - rect.left) / rect.width) * WIDTH
    const viewBoxY = ((clientY - rect.top) / rect.height) * HEIGHT
    return {
      x: (viewBoxX - transform.x) / transform.k,
      y: (viewBoxY - transform.y) / transform.k,
    }
  }

  const handlePointerDown = (node: GraphNode, e: React.PointerEvent) => {
    (e.target as Element).setPointerCapture(e.pointerId)
    draggingRef.current = node
    simulationRef.current?.alphaTarget(0.3).restart()
  }

  const handlePointerMove = (e: React.PointerEvent) => {
    const node = draggingRef.current
    if (!node) return
    const { x, y } = toSvgPoint(e.clientX, e.clientY)
    node.fx = x
    node.fy = y
  }

  const handlePointerUp = () => {
    draggingRef.current = null
    simulationRef.current?.alphaTarget(0)
  }

  const lastSim = [...traceEvents].reverse().find(e => e.layer === 'simulation')
  const involvedTypes = lastSim?.output_summary?.involved_types as
    | { mutated: string[]; referenced: string[] }
    | undefined

  const nodeColor = (id: string) => {
    if (involvedTypes?.mutated?.includes(id)) return { fill: '#fef3c7', stroke: '#d97706' }
    if (involvedTypes?.referenced?.includes(id)) return { fill: '#dbeafe', stroke: '#2563eb' }
    return { fill: '#eef2ff', stroke: '#6366f1' }
  }

  if (loading) {
    return <div className="h-full flex items-center justify-center text-gray-400 text-sm">加载本体结构中...</div>
  }
  if (error) {
    return <div className="h-full flex items-center justify-center text-gray-400 text-sm">本体信息加载失败，请重试</div>
  }
  if (objectTypes.length === 0) {
    return <div className="h-full flex items-center justify-center text-gray-400 text-sm">当前本体没有可视化的对象类型</div>
  }

  return (
    <div className="h-full flex flex-col overflow-hidden">
      {involvedTypes && (
        <div className="flex items-center gap-4 px-3 py-1.5 text-xs text-gray-500 border-b bg-gray-50 flex-shrink-0">
          <span className="flex items-center gap-1">
            <span className="w-2.5 h-2.5 rounded-full bg-amber-200 border border-amber-600 inline-block" />
            本次模拟修改
          </span>
          <span className="flex items-center gap-1">
            <span className="w-2.5 h-2.5 rounded-full bg-blue-100 border border-blue-600 inline-block" />
            本次模拟引用
          </span>
        </div>
      )}
      <div className="flex-1 relative overflow-hidden">
        <svg
          ref={svgRef}
          viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
          className="w-full h-full"
          onPointerMove={handlePointerMove}
          onPointerUp={handlePointerUp}
        >
          <defs>
            <marker id="ontology-graph-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
              <path d="M 0 0 L 10 5 L 0 10 z" fill="#a5b4fc" />
            </marker>
          </defs>
          <g transform={`translate(${transform.x}, ${transform.y}) scale(${transform.k})`}>
            {renderLinks.map((link, i) => {
              const source = link.source as GraphNode
              const target = link.target as GraphNode
              if (typeof source === 'string' || typeof target === 'string') return null
              if (source.x == null || source.y == null || target.x == null || target.y == null) return null
              return (
                <g key={i}>
                  <line
                    x1={source.x} y1={source.y} x2={target.x} y2={target.y}
                    stroke="#a5b4fc" strokeWidth={1.5} markerEnd="url(#ontology-graph-arrow)"
                  />
                  <text
                    x={(source.x + target.x) / 2}
                    y={(source.y + target.y) / 2}
                    className="fill-gray-400 text-[9px]"
                    textAnchor="middle"
                  >
                    {link.label}
                  </text>
                </g>
              )
            })}
            {nodes.map(node => {
              const color = nodeColor(node.id)
              return (
                <g
                  key={node.id}
                  data-graph-node="true"
                  transform={`translate(${node.x || 0}, ${node.y || 0})`}
                  onPointerDown={e => handlePointerDown(node, e)}
                  onMouseEnter={() => setHover({ node, x: node.x || 0, y: node.y || 0 })}
                  onMouseLeave={() => setHover(null)}
                  className="cursor-move"
                >
                  <circle r={28} fill={color.fill} stroke={color.stroke} strokeWidth={2} />
                  <text textAnchor="middle" dy="0.35em" className="fill-gray-700 text-[11px] font-medium select-none">
                    {node.id}
                  </text>
                </g>
              )
            })}
          </g>
        </svg>
        {hover && (
          <div
            className="absolute z-10 bg-white border rounded-lg shadow-lg p-3 text-xs max-w-xs pointer-events-none"
            style={{
              left: `${((hover.x * transform.k + transform.x) / WIDTH) * 100}%`,
              top: `${((hover.y * transform.k + transform.y) / HEIGHT) * 100}%`,
            }}
          >
            <div className="font-semibold text-gray-700 mb-1">{hover.node.id}</div>
            {hover.node.description && (
              <div className="text-gray-500 mb-2">{hover.node.description}</div>
            )}
            <div className="space-y-0.5">
              {hover.node.properties.map(p => (
                <div key={p.name} className="text-gray-600">
                  <span className="font-medium">{p.name}</span>
                  <span className="text-gray-400"> : {p.type}</span>
                  {p.description && <span className="text-gray-400"> — {p.description}</span>}
                </div>
              ))}
            </div>
          </div>
        )}
        <div className="absolute bottom-3 right-3 flex flex-col gap-1 z-10">
          <button
            onClick={() => zoomBy(1.2)}
            className="w-7 h-7 flex items-center justify-center rounded-md border bg-white shadow text-gray-600 hover:bg-gray-50"
            title="放大"
          >
            +
          </button>
          <button
            onClick={() => zoomBy(1 / 1.2)}
            className="w-7 h-7 flex items-center justify-center rounded-md border bg-white shadow text-gray-600 hover:bg-gray-50"
            title="缩小"
          >
            −
          </button>
          <button
            onClick={resetZoom}
            className="w-7 h-7 flex items-center justify-center rounded-md border bg-white shadow text-gray-600 hover:bg-gray-50 text-[11px]"
            title="重置视图"
          >
            ⟲
          </button>
        </div>
      </div>
    </div>
  )
}
