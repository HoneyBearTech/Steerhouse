import {
  Background,
  Controls,
  type Edge,
  Handle,
  MiniMap,
  type Node,
  type NodeProps,
  Position,
  ReactFlow,
  ReactFlowProvider,
  useReactFlow,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { ChevronDown, ChevronRight } from "lucide-react";
import * as React from "react";

import { OriginBadge } from "@/components/origin-badge";
import { Button } from "@/components/ui/button";
import { api, ApiError, type InventoryGraph } from "@/lib/api";
import { useTheme } from "@/lib/theme";
import {
  ancestorsOf,
  buildDiagram,
  GROUP_HEIGHT,
  GROUP_WIDTH,
  type GroupNodeData,
  HOST_HEIGHT,
  HOST_WIDTH,
  type HostNodeData,
  initialExpanded,
  type MoreNodeData,
} from "@/lib/group-diagram";
import { GROUP_BOTH_TITLE, type GroupIndex } from "@/lib/group-graph";
import { cn } from "@/lib/utils";

interface Actions {
  select: (name: string) => void;
  toggle: (name: string) => void;
}

// The node components are created once (React Flow wants a stable nodeTypes object), so they
// reach the page's callbacks through a context.
const ActionsContext = React.createContext<Actions>({ select: () => undefined, toggle: () => undefined });

// Edges meet nodes at these; nobody connects or drags them, so they stay invisible.
const HIDDEN_HANDLE = "pointer-events-none! h-px! w-px! min-h-0! min-w-0! border-0! bg-transparent!";

function GroupNode({ data }: NodeProps<Node<GroupNodeData>>) {
  const { select, toggle } = React.useContext(ActionsContext);
  const plural = data.hosts === 1 ? "host" : "hosts";
  return (
    <div
      className={cn(
        "flex h-[52px] w-[240px] items-center gap-1 rounded-md border bg-card px-2 text-card-foreground",
        data.selected ? "border-primary ring-2 ring-ring" : "border-border",
      )}
    >
      <Handle type="target" position={Position.Left} isConnectable={false} className={HIDDEN_HANDLE} />
      {data.children > 0 ? (
        <button
          type="button"
          className="nodrag nopan flex size-6 shrink-0 items-center justify-center rounded text-muted-foreground hover:bg-muted focus-visible:outline-2 focus-visible:outline-ring"
          aria-label={`${data.expanded ? "Hide" : "Show"} the ${data.children} group${data.children === 1 ? "" : "s"} below ${data.name}`}
          aria-expanded={data.expanded}
          onClick={() => toggle(data.name)}
        >
          {data.expanded ? <ChevronDown className="size-4" /> : <ChevronRight className="size-4" />}
        </button>
      ) : (
        <span className="size-6 shrink-0" aria-hidden="true" />
      )}
      <button
        type="button"
        className="nodrag nopan flex min-w-0 flex-1 flex-col items-start rounded px-1 text-left hover:bg-muted focus-visible:outline-2 focus-visible:outline-ring"
        aria-current={data.selected ? "true" : undefined}
        onClick={() => select(data.name)}
      >
        <span className="w-full truncate font-mono text-sm" title={data.name}>
          {data.name}
        </span>
        <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
          {data.hosts} {plural}
          <OriginBadge origin={data.origin} bothTitle={GROUP_BOTH_TITLE} />
        </span>
      </button>
      <Handle type="source" position={Position.Right} isConnectable={false} className={HIDDEN_HANDLE} />
    </div>
  );
}

function HostNode({ data }: NodeProps<Node<HostNodeData>>) {
  return (
    <div
      className="flex h-8 w-[176px] items-center rounded-md border border-border bg-muted px-2 font-mono text-xs"
      title={`${data.hostname} (in ${data.group} or a group below it)`}
    >
      <Handle type="target" position={Position.Left} isConnectable={false} className={HIDDEN_HANDLE} />
      <span className="truncate">{data.hostname}</span>
    </div>
  );
}

function MoreNode({ data }: NodeProps<Node<MoreNodeData>>) {
  return (
    <div className="flex h-8 w-[176px] items-center rounded-md border border-dashed border-border px-2 text-xs text-muted-foreground">
      <Handle type="target" position={Position.Left} isConnectable={false} className={HIDDEN_HANDLE} />
      and {data.remaining} more (see the list)
    </div>
  );
}

// Not "group": React Flow styles that name itself (a grey box behind the node).
const NODE_TYPES = { "diagram-group": GroupNode, "diagram-host": HostNode, "diagram-more": MoreNode };

/** Whether the screen is wider than a phone (the minimap would cover the diagram on one). */
function useRoomy() {
  const query = "(min-width: 640px)";
  const [roomy, setRoomy] = React.useState(() => window.matchMedia?.(query).matches ?? true);
  React.useEffect(() => {
    const list = window.matchMedia?.(query);
    if (!list) return;
    const update = () => setRoomy(list.matches);
    list.addEventListener("change", update);
    return () => list.removeEventListener("change", update);
  }, []);
  return roomy;
}

function reducedMotion() {
  return window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false;
}

/** Fits the view to the nodes whenever the set of nodes changes (not on every selection). */
function FitOnChange({ signature }: { signature: string }) {
  const { fitView } = useReactFlow();
  React.useEffect(() => {
    if (!signature) return;
    const frame = requestAnimationFrame(() =>
      fitView({ padding: 0.15, maxZoom: 1, duration: reducedMotion() ? 0 : 200 }),
    );
    return () => cancelAnimationFrame(frame);
  }, [signature, fitView]);
  return null;
}

interface HostsState {
  group: string;
  names: string[];
  total: number;
}

/** The inventory's groups as a pan-and-zoom diagram. The tree beside it is the accessible way in. */
export default function InventoryDiagram({
  graph,
  index,
  inventoryId,
  selected,
  onSelect,
}: {
  graph: InventoryGraph;
  index: GroupIndex;
  inventoryId: number;
  selected: string | null;
  onSelect: (name: string) => void;
}) {
  const [expanded, setExpanded] = React.useState(() => initialExpanded(graph, index));
  const [hosts, setHosts] = React.useState<HostsState | null>(null);
  const roomy = useRoomy();
  const { resolved } = useTheme();
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  // A group picked elsewhere (the tree, a link) must be drawn: open the groups above it, once per
  // pick (set while rendering, so the user can fold them again afterwards).
  const [openedFor, setOpenedFor] = React.useState<string | null>(null);
  if (selected !== openedFor) {
    setOpenedFor(selected);
    if (selected && index.byName.has(selected)) {
      const missing = [...ancestorsOf(selected, index)].filter((name) => !expanded.has(name));
      if (missing.length > 0) setExpanded(new Set([...expanded, ...missing]));
    }
  }

  const shownHosts = hosts && hosts.group === selected ? hosts : null;
  const diagram = React.useMemo(
    () => buildDiagram({ graph, index, expanded, selected, hosts: shownHosts }),
    [graph, index, expanded, selected, shownHosts],
  );
  const actions = React.useMemo<Actions>(
    () => ({
      select: onSelect,
      toggle: (name) =>
        setExpanded((current) => {
          const next = new Set(current);
          if (!next.delete(name)) next.add(name);
          return next;
        }),
    }),
    [onSelect],
  );

  // Sizes are known up front, so the first fit sees every node instead of waiting to measure them.
  const nodes = React.useMemo(
    () =>
      diagram.nodes.map((node) => ({
        ...node,
        type: `diagram-${node.type}`,
        ...(node.type === "group" ? { width: GROUP_WIDTH, height: GROUP_HEIGHT } : { width: HOST_WIDTH, height: HOST_HEIGHT }),
      })) as unknown as Node[],
    [diagram.nodes],
  );
  const edges = React.useMemo<Edge[]>(
    () =>
      diagram.edges.map((edge) => ({
        id: edge.id,
        source: edge.source,
        target: edge.target,
        type: "smoothstep",
        style: {
          stroke: edge.highlighted ? "var(--color-primary)" : "var(--color-border)",
          strokeWidth: edge.highlighted ? 2 : 1.5,
        },
      })),
    [diagram.edges],
  );
  // Fit again when nodes appear or go, not when only the selection moves.
  const signature = React.useMemo(() => diagram.nodes.map((n) => n.id).join("|"), [diagram.nodes]);

  async function loadHosts() {
    if (!selected) return;
    setLoading(true);
    setError(null);
    try {
      const page = await api.inventoryHosts(inventoryId, "", 1, selected);
      setHosts({ group: selected, names: page.hosts.map((h) => h.name), total: page.total });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
        <span className="min-w-0 flex-1">
          Pan by dragging, zoom with the buttons or ctrl + scroll. The tree has the same groups and works with the
          keyboard and screen readers.
        </span>
        {selected && index.byName.has(selected) && (
          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={loading}
            onClick={() => (shownHosts ? setHosts(null) : void loadHosts())}
          >
            {shownHosts ? "Hide hosts" : loading ? "Loading hosts…" : `Show hosts of ${selected}`}
          </Button>
        )}
      </div>
      {error && <p className="text-sm text-destructive">{error}</p>}
      {diagram.hidden > 0 && (
        <p className="text-xs text-muted-foreground">
          {diagram.hidden} group{diagram.hidden === 1 ? " is" : "s are"} folded away: open a group with its arrow.
        </p>
      )}
      <section
        aria-label="Group diagram"
        data-diagram
        className="relative h-[60vh] min-h-72 overflow-hidden rounded-md border border-border bg-background"
      >
        <ActionsContext.Provider value={actions}>
          <ReactFlowProvider>
            <ReactFlow
              nodes={nodes}
              edges={edges}
              nodeTypes={NODE_TYPES}
              colorMode={resolved}
              fitView
              fitViewOptions={{ padding: 0.15, maxZoom: 1 }}
              minZoom={0.1}
              maxZoom={1.5}
              nodesDraggable={false}
              nodesConnectable={false}
              nodesFocusable={false}
              edgesFocusable={false}
              elementsSelectable={false}
              zoomOnScroll={false}
              preventScrolling={false}
              onlyRenderVisibleElements
            >
              <FitOnChange signature={signature} />
              <Background gap={24} />
              <Controls showInteractive={false} />
              {roomy && <MiniMap pannable zoomable nodeColor="var(--color-secondary)" maskColor="color-mix(in srgb, var(--color-background) 70%, transparent)" />}
            </ReactFlow>
          </ReactFlowProvider>
        </ActionsContext.Provider>
      </section>
    </div>
  );
}
