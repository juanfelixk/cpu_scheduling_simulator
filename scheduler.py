from dataclasses import dataclass
from typing import List, Tuple
import copy

@dataclass
class Process:
    pid: str
    arrival: int
    burst: int
    priority: int = 0

@dataclass
class ProcessResult:
    pid: str
    arrival: int
    burst: int
    start: int
    finish: int

    @property
    def turnaround_time(self) -> int:
        return self.finish - self.arrival

    @property
    def waiting_time(self) -> int:
        return self.turnaround_time - self.burst

@dataclass
class ScheduleResult:
    algorithm: str
    gantt: List[Tuple[str, int, int]] # (pid, start, end)
    process_results: List[ProcessResult]

    @property
    def avg_waiting_time(self) -> float:
        if not self.process_results:
            return 0.0
        return sum(p.waiting_time for p in self.process_results) / len(self.process_results)

    @property
    def avg_turnaround_time(self) -> float:
        if not self.process_results:
            return 0.0
        return sum(p.turnaround_time for p in self.process_results) / len(self.process_results)

    @property
    def cpu_utilization(self) -> float:
        if not self.gantt:
            return 0.0
        total_span = self.gantt[-1][2]
        busy = sum(end - start for pid, start, end in self.gantt if pid != "IDLE")
        return (busy / total_span * 100) if total_span > 0 else 0.0

def run_algorithm(algorithm: str, processes: List[Process], quantum: int = 2) -> ScheduleResult:
    if not processes:
        return ScheduleResult(algorithm=algorithm, gantt=[], process_results=[])
    procs = copy.deepcopy(processes)
    algo = algorithm.upper().replace(" ", "")
    if "FCFS" in algo:
        return fcfs(procs)
    elif "SJF" in algo:
        return sjf(procs)
    elif "RR" in algo:
        return round_robin(procs, quantum)
    elif "PRIORITY" in algo:
        return priority(procs)
    else:
        raise ValueError(f"Unknown algorithm: {algorithm!r}")

def _insert_idle(gantt: List[Tuple[str, int, int]]) -> List[Tuple[str, int, int]]:
    """Fill gaps between gantt blocks with IDLE entries."""
    result = []
    for i, (pid, start, end) in enumerate(gantt):
        if i == 0 and start > 0:
            result.append(("IDLE", 0, start))
        elif i > 0 and gantt[i-1][2] < start:
            result.append(("IDLE", gantt[i-1][2], start))
        result.append((pid, start, end))
    return result

def fcfs(processes: List[Process]) -> ScheduleResult:
    queue = sorted(processes, key=lambda p: (p.arrival, p.pid))
    gantt: List[Tuple[str, int, int]] = []
    results: List[ProcessResult] = []
    clock = 0
    for p in queue:
        if clock < p.arrival:
            clock = p.arrival
        start = clock
        finish = start + p.burst
        gantt.append((p.pid, start, finish))
        results.append(ProcessResult(p.pid, p.arrival, p.burst, start, finish))
        clock = finish
    return ScheduleResult("FCFS", _insert_idle(gantt), results)

def sjf(processes: List[Process]) -> ScheduleResult:
    remaining = sorted(processes, key=lambda p: p.arrival)
    gantt: List[Tuple[str, int, int]] = []
    results: List[ProcessResult] = []
    clock = 0
    done = set()
    while len(done) < len(remaining):
        ready = [p for p in remaining if p.arrival <= clock and p.pid not in done]
        if not ready:
            next_arrival = min(p.arrival for p in remaining if p.pid not in done)
            clock = next_arrival
            continue
        chosen = min(ready, key=lambda p: (p.burst, p.arrival, p.pid))
        start = clock
        finish = start + chosen.burst
        gantt.append((chosen.pid, start, finish))
        results.append(ProcessResult(chosen.pid, chosen.arrival, chosen.burst, start, finish))
        clock = finish
        done.add(chosen.pid)
    return ScheduleResult("SJF", _insert_idle(gantt), results)

def round_robin(processes: List[Process], quantum: int) -> ScheduleResult:
    if quantum <= 0:
        quantum = 1

    @dataclass
    class _State:
        proc: Process
        remaining: int
        enqueued: bool = False

    states = {p.pid: _State(p, p.burst) for p in processes}
    arrival_order = sorted(processes, key=lambda p: (p.arrival, p.pid))
    gantt: List[Tuple[str, int, int]] = []
    first_start: dict = {}
    queue: List[str] = []
    clock = 0
    done: set = set()

    def enqueue_arrivals():
        for p in arrival_order:
            s = states[p.pid]
            if p.arrival <= clock and not s.enqueued and p.pid not in done:
                queue.append(p.pid)
                s.enqueued = True

    enqueue_arrivals()
    if not queue:
        clock = arrival_order[0].arrival
        enqueue_arrivals()

    while len(done) < len(processes):
        if not queue:
            future = [p for p in arrival_order if p.pid not in done and not states[p.pid].enqueued]
            if not future:
                break
            clock = future[0].arrival
            enqueue_arrivals()
            continue
        pid = queue.pop(0)
        s = states[pid]
        if pid not in first_start:
            first_start[pid] = clock
        run_time = min(quantum, s.remaining)
        start = clock
        finish = start + run_time
        gantt.append((pid, start, finish))
        clock = finish
        s.remaining -= run_time
        enqueue_arrivals()
        if s.remaining == 0:
            done.add(pid)
        else:
            queue.append(pid)

    results: List[ProcessResult] = []
    for p in processes:
        last_finish = max(end for lbl, _, end in gantt if lbl == p.pid)
        fs = first_start.get(p.pid, p.arrival)
        results.append(ProcessResult(p.pid, p.arrival, p.burst, fs, last_finish))
    pid_order = {p.pid: i for i, p in enumerate(arrival_order)}
    results.sort(key=lambda r: pid_order[r.pid])
    return ScheduleResult("Round Robin", _insert_idle(gantt), results)

def priority(processes: List[Process]) -> ScheduleResult:
    remaining = sorted(processes, key=lambda p: p.arrival)
    gantt: List[Tuple[str, int, int]] = []
    results: List[ProcessResult] = []
    clock = 0
    done = set()
    while len(done) < len(remaining):
        ready = [p for p in remaining if p.arrival <= clock and p.pid not in done]
        if not ready:
            next_arrival = min(p.arrival for p in remaining if p.pid not in done)
            clock = next_arrival
            continue
        chosen = min(ready, key=lambda p: (p.priority, p.arrival, p.pid))
        start = clock
        finish = start + chosen.burst
        gantt.append((chosen.pid, start, finish))
        results.append(ProcessResult(chosen.pid, chosen.arrival, chosen.burst, start, finish))
        clock = finish
        done.add(chosen.pid)
    return ScheduleResult("Priority", _insert_idle(gantt), results)