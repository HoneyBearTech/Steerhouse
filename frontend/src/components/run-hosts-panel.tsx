import * as React from "react";

import { Badge, type BadgeProps } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableCell, TableHead } from "@/components/ui/table";
import { api, ApiError, type HostResult, type HostStatus, type Run, type RunHosts } from "@/lib/api";
import { STATUS_VARIANT } from "@/lib/runs";
import { compareRuns, hostsDiffer, STATUS_LABEL, type CompareCell } from "@/lib/run-hosts";

const REFRESH_MS = 3000;

const RESULT_VARIANT: Record<HostStatus, BadgeProps["variant"]> = {
  ok: "ok",
  changed: "changed",
  failed: "failed",
  ignored: "outline",
  skipped: "skipped",
  unreachable: "failed",
};

// A run's results, refreshed every few seconds until the run has finished.
function useRunHosts(runId: number): { data: RunHosts | null; error: string | null } {
  const [state, setState] = React.useState<{ id: number; data: RunHosts | null; error: string | null }>({
    id: runId,
    data: null,
    error: null,
  });

  React.useEffect(() => {
    let active = true;
    let timer: ReturnType<typeof setTimeout>;

    async function load() {
      try {
        const data = await api.getRunHosts(runId);
        if (!active) return;
        setState({ id: runId, data, error: null });
        if (!data.complete) timer = setTimeout(load, REFRESH_MS);
      } catch (error) {
        if (!active) return;
        setState({
          id: runId,
          data: null,
          error: error instanceof ApiError ? error.message : "Could not load the results.",
        });
      }
    }
    load();

    return () => {
      active = false;
      clearTimeout(timer);
    };
  }, [runId]);

  // Until the new run's answer arrives, the old one is not shown as its results.
  return state.id === runId ? state : { data: null, error: null };
}

function StatusBadge({ result }: { result: HostResult | undefined }) {
  if (!result) return <span className="text-muted-foreground">—</span>;
  return <Badge variant={RESULT_VARIANT[result.status]}>{STATUS_LABEL[result.status]}</Badge>;
}

interface Picked {
  title: string;
  host: string;
  results: { label: string | null; result: HostResult | undefined }[];
}

function CellDialog({ picked, onClose }: { picked: Picked | null; onClose: () => void }) {
  return (
    <Dialog open={picked !== null} onOpenChange={(open) => !open && onClose()}>
      <DialogContent>
        {picked && (
          <>
            <DialogHeader>
              <DialogTitle className="wrap-anywhere">{picked.title}</DialogTitle>
              <DialogDescription className="wrap-anywhere">on {picked.host}</DialogDescription>
            </DialogHeader>
            <div className="flex flex-col gap-3">
              {picked.results.map(({ label, result }) => (
                <div key={label ?? "only"} className="flex flex-col gap-1">
                  {label && <p className="text-sm font-medium">{label}</p>}
                  <StatusBadge result={result} />
                  {result?.msg ? (
                    <pre className="max-h-60 overflow-auto whitespace-pre-wrap rounded-md bg-muted p-3 font-mono text-xs wrap-anywhere">
                      {result.msg}
                    </pre>
                  ) : (
                    result && <p className="text-sm text-muted-foreground">The module gave no message.</p>
                  )}
                </div>
              ))}
            </div>
            <DialogFooter>
              <Button variant="secondary" onClick={onClose}>
                Close
              </Button>
            </DialogFooter>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}

function rowTitle(row: { name: string; role: string | null; handler: boolean }): string {
  return `${row.role ? `${row.role} : ` : ""}${row.name}${row.handler ? " (handler)" : ""}`;
}

function Notes({ data }: { data: RunHosts }) {
  return (
    <>
      {data.lost_events > 0 && (
        <p className="text-sm text-muted-foreground">
          {data.lost_events} event{data.lost_events === 1 ? "" : "s"} too large to keep or left out of the
          output: some cells may be missing.
        </p>
      )}
      {data.truncated && (
        <p className="text-sm text-muted-foreground">
          This run has more tasks or hosts than are listed here. The output has all of them.
        </p>
      )}
    </>
  );
}

function CompareCellView({ cell }: { cell: CompareCell }) {
  if (cell.state === "same") return <StatusBadge result={cell.a} />;
  return (
    <span className="flex flex-wrap items-center gap-1">
      <StatusBadge result={cell.a} />
      <span aria-label="became">→</span>
      <StatusBadge result={cell.b} />
    </span>
  );
}

function RunPicker({
  run,
  onPick,
  onClose,
}: {
  run: Run;
  onPick: (id: number) => void;
  onClose: () => void;
}) {
  const [all, setAll] = React.useState(false);
  // What was loaded, and for which setting: a changed setting shows "loading" until its answer is in.
  const [loaded, setLoaded] = React.useState<{ all: boolean; runs: Run[] | null; error: string | null } | null>(
    null,
  );
  const [choice, setChoice] = React.useState("");
  const current = loaded?.all === all ? loaded : null;
  const runs = current?.runs ?? null;
  const error = current?.error ?? null;

  React.useEffect(() => {
    let active = true;
    // A deleted playbook leaves its runs with no id: only "every run" can find them.
    const options = all || run.playbook_id === null ? { limit: 50 } : { playbook_id: run.playbook_id, limit: 50 };
    api
      .listRuns(options)
      .then((found) => {
        if (!active) return;
        const others = found.filter((other) => other.id !== run.id);
        setLoaded({ all, runs: others, error: null });
        // The run before this one, else the newest other.
        setChoice(String((others.find((other) => other.id < run.id) ?? others[0])?.id ?? ""));
      })
      .catch(() => active && setLoaded({ all, runs: null, error: "Could not load the runs." }));
    return () => {
      active = false;
    };
  }, [all, run.id, run.playbook_id]);

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Compare run #{run.id} with…</DialogTitle>
          <DialogDescription>
            {all ? "Any run in this project, newest first." : `Runs of ${run.playbook_name}, newest first.`}
          </DialogDescription>
        </DialogHeader>
        <div className="flex flex-col gap-4">
          <div className="flex items-center gap-2">
            <Checkbox id="compare-all" checked={all} onCheckedChange={(value) => setAll(value === true)} />
            <Label htmlFor="compare-all">Show every run in this project</Label>
          </div>
          {error && <p className="text-sm text-destructive">{error}</p>}
          {runs && runs.length === 0 && (
            <p className="text-sm text-muted-foreground">There is no other run to compare with.</p>
          )}
          {runs && runs.length > 0 && (
            <div className="flex flex-col gap-2">
              <Label htmlFor="compare-run">Run</Label>
              <Select value={choice} onValueChange={setChoice}>
                <SelectTrigger id="compare-run">
                  <SelectValue placeholder="Pick a run" />
                </SelectTrigger>
                <SelectContent>
                  {runs.map((other) => (
                    <SelectItem key={other.id} value={String(other.id)}>
                      #{other.id} · {other.status.replace("_", " ")} · {other.playbook_name} →{" "}
                      {other.inventory_name} · {new Date(other.created_at).toLocaleString()}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          )}
        </div>
        <DialogFooter>
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button disabled={!choice} onClick={() => onPick(Number(choice))}>
            Compare
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// "By host": what each host did in each task of the run, and a side-by-side with another run.
export function RunHostsPanel({
  run,
  compareId,
  onCompare,
}: {
  run: Run;
  compareId: number | null;
  onCompare: (id: number | null) => void;
}) {
  const mine = useRunHosts(run.id);
  const theirs = useRunHosts(compareId ?? 0);
  const [loadedOther, setLoadedOther] = React.useState<Run | null>(null);
  const [picking, setPicking] = React.useState(false);
  const [onlyDiffering, setOnlyDiffering] = React.useState<boolean | null>(null);
  const [picked, setPicked] = React.useState<Picked | null>(null);

  React.useEffect(() => {
    if (compareId === null) return;
    let active = true;
    api
      .getRun(compareId)
      .then((found) => active && setLoadedOther(found))
      .catch(() => undefined);
    return () => {
      active = false;
    };
  }, [compareId]);
  const other = loadedOther?.id === compareId ? loadedOther : null;

  const comparing = compareId !== null;
  const onlyRows = onlyDiffering ?? comparing;
  const loaded = mine.data && (!comparing || theirs.data);
  const error = mine.error ?? (comparing ? theirs.error : null);

  const comparison = React.useMemo(
    () => (mine.data && theirs.data && comparing ? compareRuns(mine.data, theirs.data) : null),
    [mine.data, theirs.data, comparing],
  );

  let body: React.ReactNode = null;
  if (error) {
    body = <p className="text-sm text-destructive">{error}</p>;
  } else if (!loaded) {
    body = <p className="text-sm text-muted-foreground">Loading…</p>;
  } else if (comparison) {
    const rows = comparison.rows.filter((row) => !onlyRows || row.differs);
    body = (
      <>
        {rows.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            {comparison.rows.length === 0
              ? "Neither run has task results yet."
              : "No task differs between the two runs."}
          </p>
        ) : (
          <Table>
            <thead>
              <tr>
                <TableHead scope="col">Task</TableHead>
                {comparison.hosts.map((host) => (
                  <TableHead key={host} scope="col" className="font-mono">
                    {host}
                  </TableHead>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row, index) => (
                <React.Fragment key={row.key}>
                  {(index === 0 || rows[index - 1]?.play !== row.play) && (
                    <tr>
                      <TableCell colSpan={comparison.hosts.length + 1} className="bg-muted/20 font-medium">
                        {row.play || "Play"}
                      </TableCell>
                    </tr>
                  )}
                  <tr className={row.differs ? "bg-status-changed/5" : undefined}>
                    <TableCell className="min-w-48 wrap-anywhere">
                      {rowTitle(row)}
                      {row.only && (
                        <Badge variant="outline" className="ml-2">
                          only in run #{row.only === "a" ? run.id : compareId}
                        </Badge>
                      )}
                      {row.differs && !row.only && <span className="sr-only"> (differs between the runs)</span>}
                    </TableCell>
                    {comparison.hosts.map((host) => {
                      const cell = row.cells[host];
                      return (
                        <TableCell key={host}>
                          {cell ? (
                            <button
                              type="button"
                              className="rounded-sm text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                              aria-label={`${rowTitle(row)} on ${host}`}
                              onClick={() =>
                                setPicked({
                                  title: rowTitle(row),
                                  host,
                                  results: [
                                    { label: `Run #${run.id}`, result: cell.a },
                                    { label: `Run #${compareId}`, result: cell.b },
                                  ],
                                })
                              }
                            >
                              <CompareCellView cell={cell} />
                            </button>
                          ) : (
                            <span className="text-muted-foreground">—</span>
                          )}
                        </TableCell>
                      );
                    })}
                  </tr>
                </React.Fragment>
              ))}
            </tbody>
          </Table>
        )}
        {mine.data && <Notes data={mine.data} />}
        {theirs.data && <Notes data={theirs.data} />}
      </>
    );
  } else if (mine.data) {
    const data = mine.data;
    const rows = data.tasks.filter((task) => !onlyRows || hostsDiffer(task));
    body = (
      <>
        {rows.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            {data.tasks.length === 0
              ? run.status === "queued" || run.status === "running"
                ? "No task has reported yet."
                : "This run has no task results."
              : "Every host did the same in every task."}
          </p>
        ) : (
          <Table>
            <thead>
              <tr>
                <TableHead scope="col">Task</TableHead>
                {data.hosts.map((host) => (
                  <TableHead key={host} scope="col" className="font-mono">
                    {host}
                  </TableHead>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((task, index) => (
                <React.Fragment key={task.key}>
                  {(index === 0 || rows[index - 1]?.play !== task.play) && (
                    <tr>
                      <TableCell colSpan={data.hosts.length + 1} className="bg-muted/20 font-medium">
                        {task.play || "Play"}
                      </TableCell>
                    </tr>
                  )}
                  <tr className={hostsDiffer(task) ? "bg-status-changed/5" : undefined}>
                    <TableCell className="min-w-48 wrap-anywhere">
                      {rowTitle(task)}
                      {hostsDiffer(task) && <span className="sr-only"> (hosts differ)</span>}
                    </TableCell>
                    {data.hosts.map((host) => {
                      const result = task.results[host];
                      return (
                        <TableCell key={host}>
                          {result ? (
                            <button
                              type="button"
                              className="rounded-sm text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                              aria-label={`${rowTitle(task)} on ${host}`}
                              onClick={() =>
                                setPicked({ title: rowTitle(task), host, results: [{ label: null, result }] })
                              }
                            >
                              <StatusBadge result={result} />
                            </button>
                          ) : (
                            <span className="text-muted-foreground">—</span>
                          )}
                        </TableCell>
                      );
                    })}
                  </tr>
                </React.Fragment>
              ))}
            </tbody>
          </Table>
        )}
        <Notes data={data} />
      </>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
        <div className="flex items-center gap-2">
          <Checkbox
            id="only-differing"
            checked={onlyRows}
            onCheckedChange={(value) => setOnlyDiffering(value === true)}
          />
          <Label htmlFor="only-differing">
            {comparing ? "Only tasks that differ between the runs" : "Only tasks where hosts differ"}
          </Label>
        </div>
        <div className="ml-auto flex flex-wrap items-center gap-2">
          {comparing && (
            <Button variant="secondary" size="sm" onClick={() => onCompare(null)}>
              Stop comparing
            </Button>
          )}
          <Button variant="secondary" size="sm" onClick={() => setPicking(true)}>
            {comparing ? "Compare with another run…" : "Compare with…"}
          </Button>
        </div>
      </div>
      {comparing && (
        <p className="text-sm text-muted-foreground">
          Comparing run #{run.id} with{" "}
          {other ? (
            <>
              run #{other.id} (<Badge variant={STATUS_VARIANT[other.status]}>{other.status.replace("_", " ")}</Badge>
              , {other.playbook_name} → {other.inventory_name})
            </>
          ) : (
            <>run #{compareId}</>
          )}
          . Each cell shows run #{run.id}, then run #{compareId} where they differ.
        </p>
      )}
      {body}
      {picking && (
        <RunPicker
          run={run}
          onClose={() => setPicking(false)}
          onPick={(id) => {
            setPicking(false);
            onCompare(id);
          }}
        />
      )}
      <CellDialog picked={picked} onClose={() => setPicked(null)} />
    </div>
  );
}
