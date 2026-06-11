import random
import customtkinter as ctk
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from scheduler import Process, ScheduleResult, run_algorithm

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

ALGORITHMS = [
    "First Come First Serve (FCFS)",
    "Shortest Job First (SJF)",
    "Round Robin (RR)",
    "Priority Scheduling",
]

ALGO_KEY = {
    "First Come First Serve (FCFS)": "FCFS",
    "Shortest Job First (SJF)": "SJF",
    "Round Robin (RR)": "RR",
    "Priority Scheduling": "Priority",
}

DESCRIPTIONS = {
    "First Come First Serve (FCFS)":
        "Processes execute in arrival order. Simple and fair, but long jobs can stall short ones (the convoy effect).",
    "Shortest Job First (SJF)":
        "Picks the process with the smallest burst time next. Minimizes average waiting time but may starve long processes.",
    "Round Robin (RR)":
        "Each process gets a fixed time quantum in cyclic order. Excellent responsiveness for interactive / time-sharing systems.",
    "Priority Scheduling":
        "Runs the highest-priority process first (lower number = higher priority). Flexible, but low-priority jobs may starve without aging.",
}

GANTT_COLORS = ["#4e79a7", "#59a14f", "#e15759", "#f1a340", "#9c6ade", "#17becf", "#ff7f0e", "#8c564b"]
GANTT_IDLE_COLOR = "#555555"
GANTT_BG = {"Dark": "#2b2b2b", "Light": "#efefef", "System": "#2b2b2b"}
PAD = 12
# initial values
SAMPLE_PROCESSES = [
    ("P1", "0", "6", "2"),
    ("P2", "1", "3", "1"),
    ("P3", "2", "8", "4"),
    ("P4", "3", "4", "3"),
]

class CPUSchedulerApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("CPU Scheduling Simulator")
        self.geometry("1200x860")
        self.minsize(960, 700)

        self._appearance = "Dark"
        self._last_result: ScheduleResult | None = None
        self._all_results: dict[str, ScheduleResult] = {}
        self._last_processes: list[Process] = []
        self._compare_quantum_active = 2
        self.process_rows: list = []

        self.scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll.pack(fill="both", expand=True, padx=PAD, pady=PAD)
        self.scroll.grid_columnconfigure(0, weight=1)

        self._build_header()
        self._build_controls()
        self._build_process_input()
        self._build_results()
        self._build_gantt()
        self._build_comparison()

        ctk.CTkFrame(self.scroll, fg_color="transparent", height=40).grid(row=99, column=0, sticky="ew")

        self._populate_sample_processes()

    def _build_header(self):
        header = ctk.CTkFrame(self.scroll, corner_radius=12)
        header.grid(row=0, column=0, sticky="ew", pady=(0, PAD))
        header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            header, text="CPU Scheduling Simulator",
            font=ctk.CTkFont(size=24, weight="bold"),
        ).grid(row=0, column=0, sticky="w", padx=PAD, pady=PAD)

        self._appearance_menu = ctk.CTkOptionMenu(
            header, values=["Dark", "Light", "System"],
            command=self._on_appearance_change, width=110,
        )
        self._appearance_menu.set("Dark")
        self._appearance_menu.grid(row=0, column=1, padx=PAD, pady=PAD, sticky="e")

    def _on_appearance_change(self, value: str):
        self._appearance = value
        ctk.set_appearance_mode(value.lower())
        if self._last_result:
            self._draw_gantt(self._last_result.gantt)

    def _build_controls(self):
        card = self._section("Algorithm & Controls", row=1)

        ctrl_row = ctk.CTkFrame(card, fg_color="transparent")
        ctrl_row.grid(row=1, column=0, sticky="ew", padx=PAD, pady=(0, 6))

        ctk.CTkLabel(ctrl_row, text="Algorithm:").pack(side="left", padx=(0, 8))
        self._algo_menu = ctk.CTkOptionMenu(
            ctrl_row, values=ALGORITHMS, width=260, command=self._on_algo_change,
        )
        self._algo_menu.set(ALGORITHMS[0])
        self._algo_menu.pack(side="left", padx=(0, 16))

        self._quantum_frame = ctk.CTkFrame(ctrl_row, fg_color="transparent")
        ctk.CTkLabel(self._quantum_frame, text="Time Quantum:").pack(side="left", padx=(0, 8))
        self._quantum_entry = ctk.CTkEntry(self._quantum_frame, width=70, placeholder_text="2")
        self._quantum_entry.pack(side="left")

        ctk.CTkButton(
            ctrl_row, text="Generate Random",
            command=self._generate_random,
        ).pack(side="left", padx=(0, 10))

        ctk.CTkButton(
            ctrl_row, text="Run Simulation",
            fg_color="#2e8b57", hover_color="#246b43",
            command=self._run_simulation,
        ).pack(side="left")

        self._desc_label = ctk.CTkLabel(card, text=DESCRIPTIONS[ALGORITHMS[0]], wraplength=1050, justify="left", text_color=("gray30", "gray70"))
        self._desc_label.grid(row=2, column=0, sticky="w", padx=PAD, pady=(4, PAD))

        self._error_label = ctk.CTkLabel(card, text="", text_color="#e15759", font=ctk.CTkFont(size=12), wraplength=1050, justify="left")
        self._error_label.grid(row=3, column=0, sticky="w", padx=PAD, pady=(0, 6))

    def _on_algo_change(self, value: str):
        self._desc_label.configure(text=DESCRIPTIONS.get(value, ""))

        # show/hide quantum input
        if value == "Round Robin (RR)":
            self._quantum_frame.pack(side="left", padx=(0, 16), before=self._quantum_frame.master.winfo_children()[-2])
        else:
            self._quantum_frame.pack_forget()

        # dim priority column when not priority scheduling
        is_priority = (value == "Priority Scheduling")
        self._set_priority_column_state(is_priority)

        if self._all_results:
            self._refresh_comparison()

    def _build_process_input(self):
        card = self._section("Process Input", row=2)

        self._input_table = ctk.CTkFrame(card, fg_color="transparent")
        self._input_table.grid(row=1, column=0, sticky="ew", padx=PAD, pady=4)
        for i in range(4):
            self._input_table.grid_columnconfigure(i, weight=1)

        for c, h in enumerate(["Process ID", "Arrival Time", "Burst Time", "Priority"]):
            ctk.CTkLabel(self._input_table, text=h, font=ctk.CTkFont(weight="bold")).grid(row=0, column=c, padx=4, pady=4, sticky="ew")

        btns = ctk.CTkFrame(card, fg_color="transparent")
        btns.grid(row=2, column=0, sticky="w", padx=PAD, pady=(4, PAD))
        ctk.CTkButton(btns, text="+ Add Process", width=130, command=lambda: self._add_input_row()).pack(side="left", padx=(0, 8))
        ctk.CTkButton(btns, text="– Remove Last", width=130, fg_color="#8b3a3a", hover_color="#6e2d2d", command=self._remove_input_row).pack(side="left")

    def _set_priority_column_state(self, enabled: bool):
        """Dim or restore Priority entries (col 3) with both bg and text color."""
        fg    = ("gray85", "gray20") if enabled else ("gray70", "gray35")
        color = ("gray10", "gray90") if enabled else ("gray50", "gray55")
        state = "normal" if enabled else "disabled"
        for row_entries in self.process_rows:
            row_entries[3].configure(state=state, fg_color=fg, text_color=color)

    def _add_input_row(self, values=("", "", "", "")):
        r = len(self.process_rows) + 1
        entries = []
        for c in range(4):
            e = ctk.CTkEntry(self._input_table, justify="center")
            e.insert(0, values[c])
            e.grid(row=r, column=c, padx=4, pady=3, sticky="ew")
            entries.append(e)
        self.process_rows.append(entries)
        # apply current priority state immediately
        is_priority = (self._algo_menu.get() == "Priority Scheduling")
        self._set_priority_column_state(is_priority)

    def _remove_input_row(self):
        if self.process_rows:
            for e in self.process_rows.pop():
                e.destroy()

    def _populate_sample_processes(self):
        while self.process_rows:
            for e in self.process_rows.pop():
                e.destroy()
        for vals in SAMPLE_PROCESSES:
            self._add_input_row(vals)

    def _generate_random(self):
        while self.process_rows:
            for e in self.process_rows.pop():
                e.destroy()
        n = random.randint(3, 6)
        for i in range(n):
            self._add_input_row((
                f"P{i+1}",
                str(random.randint(0, 5)),
                str(random.randint(1, 10)),
                str(random.randint(1, 5)),
            ))

    def _build_results(self):
        card = self._section("Results", row=3)

        self._results_table_frame = ctk.CTkFrame(card)
        self._results_table_frame.grid(row=1, column=0, sticky="ew", padx=PAD, pady=4)
        self._build_results_table(None)

        self._metrics_frame = ctk.CTkFrame(card, fg_color="transparent")
        self._metrics_frame.grid(row=2, column=0, sticky="ew", padx=PAD, pady=(PAD, PAD))
        for i in range(3):
            self._metrics_frame.grid_columnconfigure(i, weight=1)

        self._metric_wt  = self._metric_card(self._metrics_frame, 0, "Average Waiting Time", "-")
        self._metric_tat = self._metric_card(self._metrics_frame, 1, "Average Turnaround Time", "-")
        self._metric_cpu = self._metric_card(self._metrics_frame, 2, "CPU Utilization", "-")

    def _build_results_table(self, result: ScheduleResult | None):
        for w in self._results_table_frame.winfo_children():
            w.destroy()

        cols = ["PID", "Arrival", "Burst", "Start", "Waiting Time", "Turnaround Time"]
        for c, h in enumerate(cols):
            self._results_table_frame.grid_columnconfigure(c, weight=1)
            ctk.CTkLabel(
                self._results_table_frame, text=h,
                font=ctk.CTkFont(weight="bold"),
                fg_color=("gray80", "gray25"), corner_radius=4,
            ).grid(row=0, column=c, padx=1, pady=1, sticky="nsew")

        if result is None:
            ctk.CTkLabel(self._results_table_frame, text="Run a simulation to see results.", text_color=("gray40", "gray60")).grid(row=1, column=0, columnspan=6, pady=8)
            return

        for r, pr in enumerate(result.process_results, start=1):
            for c, val in enumerate([
                pr.pid, pr.arrival, pr.burst, pr.start,
                pr.waiting_time, pr.turnaround_time,
            ]):
                ctk.CTkLabel(self._results_table_frame, text=str(val)).grid(row=r, column=c, padx=1, pady=3, sticky="nsew")

    def _metric_card(self, parent, col: int, title: str, value: str):
        frame = ctk.CTkFrame(parent, corner_radius=10)
        frame.grid(row=0, column=col, padx=6, sticky="ew")
        ctk.CTkLabel(frame, text=title, text_color=("gray30", "gray70")).pack(pady=(PAD, 2))
        val_lbl = ctk.CTkLabel(frame, text=value, font=ctk.CTkFont(size=26, weight="bold"))
        val_lbl.pack(pady=(0, PAD))
        return val_lbl

    def _update_metrics(self, result: ScheduleResult):
        self._metric_wt.configure(text=f"{result.avg_waiting_time:.2f}")
        self._metric_tat.configure(text=f"{result.avg_turnaround_time:.2f}")
        self._metric_cpu.configure(text=f"{result.cpu_utilization:.1f}%")

    def _build_gantt(self):
        self._gantt_card = self._section("Gantt Chart", row=4)
        self._gantt_widget_frame = ctk.CTkFrame(
            self._gantt_card, fg_color="transparent")
        self._gantt_widget_frame.grid(
            row=1, column=0, sticky="ew", padx=PAD, pady=(0, PAD))
        self._gantt_canvas_widget = None
        self._gantt_placeholder = ctk.CTkLabel(self._gantt_widget_frame, text="Gantt chart will appear here after running a simulation.", text_color=("gray40", "gray60"))
        self._gantt_placeholder.pack(pady=20)

    def _draw_gantt(self, gantt: list):
        if self._gantt_canvas_widget:
            self._gantt_canvas_widget.get_tk_widget().destroy()
            self._gantt_canvas_widget = None
        if self._gantt_placeholder:
            self._gantt_placeholder.destroy()
            self._gantt_placeholder = None

        bg = GANTT_BG.get(self._appearance, "#2b2b2b")
        tick_color = "white" if self._appearance != "Light" else "#222222"
        label_color = "white" if self._appearance != "Light" else "#111111"

        unique_pids = list(dict.fromkeys(pid for pid, _, _ in gantt if pid != "IDLE"))
        pid_color = {pid: GANTT_COLORS[i % len(GANTT_COLORS)] for i, pid in enumerate(unique_pids)}

        fig = Figure(figsize=(10, 1.9), dpi=100, facecolor=bg)
        ax = fig.add_subplot(111)
        ax.set_facecolor(bg)

        for pid, start, end in gantt:
            color = GANTT_IDLE_COLOR if pid == "IDLE" else pid_color[pid]
            ax.barh(0, end - start, left=start, height=0.5, color=color, edgecolor=bg, linewidth=0.8)
            lbl = "Idle" if pid == "IDLE" else pid
            ax.text((start + end) / 2, 0, lbl, ha="center", va="center", color="#aaaaaa" if pid == "IDLE" else label_color, fontsize=9, fontweight="bold")

        ticks = sorted({s for _, s, _ in gantt} | {e for _, _, e in gantt})
        ax.set_xticks(ticks)
        ax.tick_params(colors=tick_color, labelsize=8)
        ax.set_yticks([])
        for spine in ax.spines.values():
            spine.set_visible(False)
        ax.set_xlim(0, ticks[-1])
        fig.tight_layout(pad=0.4)

        canvas = FigureCanvasTkAgg(fig, master=self._gantt_widget_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)
        self._gantt_canvas_widget = canvas

    def _build_comparison(self):
        card = self._section("Algorithm Comparison", row=5)

        top = ctk.CTkFrame(card, fg_color="transparent")
        top.grid(row=1, column=0, sticky="ew", padx=PAD, pady=(0, 6))

        ctk.CTkLabel(top, text="Compare with:").pack(side="left", padx=(0, 8))
        self._compare_menu = ctk.CTkOptionMenu(top, values=ALGORITHMS[1:], width=260, command=self._on_compare_algo_change)
        self._compare_menu.set(ALGORITHMS[1])
        self._compare_menu.pack(side="left", padx=(0, 8))

        # Comparison quantum frame — only shown when comparison algo is RR
        self._cmp_quantum_frame = ctk.CTkFrame(top, fg_color="transparent")
        ctk.CTkLabel(self._cmp_quantum_frame, text="Time Quantum:").pack(side="left", padx=(0, 8))
        self._compare_quantum_entry = ctk.CTkEntry(self._cmp_quantum_frame, width=70, placeholder_text="2")
        self._compare_quantum_entry.pack(side="left", padx=(0, 8))
        self._apply_quantum_btn = ctk.CTkButton(self._cmp_quantum_frame, text="Apply quantum", width=130, fg_color = "#2e8b57", hover_color="#246b43", state = "disabled", command = self._apply_compare_quantum)
        self._apply_quantum_btn.pack(side="left")

        self._compare_quantum_entry.bind("<KeyRelease>", lambda _: self._on_compare_quantum_key())

        self._compare_holder = ctk.CTkFrame(card, fg_color="transparent")
        self._compare_holder.grid(row=2, column=0, sticky="ew", padx=PAD, pady=(0, PAD))
        self._compare_holder.grid_columnconfigure((0, 1), weight=1)
        self._refresh_comparison()

    def _on_compare_algo_change(self, value: str):
        if value == "Round Robin (RR)":
            self._cmp_quantum_frame.pack(side="left", padx=(8, 0))
            main_q = self._quantum_entry.get().strip() or "2"
            self._compare_quantum_entry.delete(0, "end")
            self._compare_quantum_entry.insert(0, main_q)
            self._compare_quantum_active = int(main_q) if main_q.isdigit() else 2
            self._apply_quantum_btn.configure(state="disabled")
        else:
            self._cmp_quantum_frame.pack_forget()
        self._refresh_comparison()

    def _on_compare_quantum_key(self):
        raw = self._compare_quantum_entry.get().strip()
        try:
            entered = int(raw)
            changed = (entered > 0 and entered != self._compare_quantum_active)
        except ValueError:
            changed = False
        self._apply_quantum_btn.configure(state="normal" if changed else "disabled")

    def _apply_compare_quantum(self):
        raw = self._compare_quantum_entry.get().strip()
        try:
            q = int(raw)
            if q <= 0:
                raise ValueError
        except ValueError:
            return
        self._compare_quantum_active = q
        self._apply_quantum_btn.configure(state="disabled")
        self._refresh_comparison()

    def _refresh_comparison(self):
        for w in self._compare_holder.winfo_children():
            w.destroy()

        sel = self._algo_menu.get()
        other = self._compare_menu.get()

        if other == sel:
            options = [a for a in ALGORITHMS if a != sel]
            other = options[0]
            self._compare_menu.configure(values=options)
            self._compare_menu.set(other)
            if other == "Round Robin (RR)":
                self._cmp_quantum_frame.pack(side="left", padx=(8, 0))
            else:
                self._cmp_quantum_frame.pack_forget()
        else:
            self._compare_menu.configure(values=[a for a in ALGORITHMS if a != sel])

        sel_result = self._all_results.get(sel)

        if other == "Round Robin (RR)" and self._last_processes:
            other_result = run_algorithm("RR", self._last_processes, quantum=self._compare_quantum_active)
        else:
            other_result = self._all_results.get(other)

        self._compare_card_widget(0, sel, "#2e8b57", sel_result)
        self._compare_card_widget(1, other, "#3b6fa0", other_result)

    def _compare_card_widget(self, col: int, algo: str, accent: str, result: ScheduleResult | None):
        c = ctk.CTkFrame(self._compare_holder, corner_radius=10)
        c.grid(row=0, column=col, padx=8, sticky="nsew")

        ctk.CTkLabel(c, text=algo, font=ctk.CTkFont(size=15, weight="bold"), text_color=accent, wraplength=420).pack(pady=(PAD, 8))

        if result is None:
            ctk.CTkLabel(c, text="Run simulation to see metrics.", text_color=("gray40", "gray60")).pack(pady=(4, PAD))
            return

        for label, val in [
            ("Avg Waiting Time",    f"{result.avg_waiting_time:.2f}"),
            ("Avg Turnaround Time", f"{result.avg_turnaround_time:.2f}"),
            ("CPU Utilization",     f"{result.cpu_utilization:.1f}%"),
        ]:
            row = ctk.CTkFrame(c, fg_color="transparent")
            row.pack(fill="x", padx=PAD, pady=3)
            ctk.CTkLabel(row, text=label, text_color=("gray30", "gray70")).pack(side="left")
            ctk.CTkLabel(row, text=val, font=ctk.CTkFont(weight="bold")).pack(side="right")
        ctk.CTkLabel(c, text="").pack(pady=2)

    def _parse_processes(self) -> list[Process] | None:
        processes = []
        for i, row in enumerate(self.process_rows):
            pid_val      = row[0].get().strip()
            arrival_val  = row[1].get().strip()
            burst_val    = row[2].get().strip()
            priority_val = row[3].get().strip()

            if not pid_val:
                self._show_error(f"Row {i+1}: Process ID cannot be empty.")
                return None
            if any(p.pid == pid_val for p in processes):
                self._show_error(f"Duplicate Process ID '{pid_val}' in row {i+1}.")
                return None
            try:
                arrival  = int(arrival_val)
                burst    = int(burst_val)
                priority = int(priority_val) if priority_val else 0
            except ValueError:
                self._show_error(
                    f"Row {i+1} ({pid_val}): Arrival, Burst, and Priority must be integers.")
                return None
            if arrival < 0:
                self._show_error(f"Row {i+1} ({pid_val}): Arrival time cannot be negative.")
                return None
            if burst <= 0:
                self._show_error(f"Row {i+1} ({pid_val}): Burst time must be > 0.")
                return None
            processes.append(Process(pid_val, arrival, burst, priority))

        if not processes:
            self._show_error("Add at least one process before running.")
            return None
        return processes

    def _get_quantum(self) -> int | None:
        raw = self._quantum_entry.get().strip()
        if not raw:
            return 2
        try:
            q = int(raw)
            if q <= 0:
                raise ValueError
            return q
        except ValueError:
            self._show_error("Time Quantum must be a positive integer.")
            return None

    def _run_simulation(self):
        self._clear_error()

        processes = self._parse_processes()
        if processes is None:
            return
        self._last_processes = processes

        quantum = self._get_quantum()
        if quantum is None:
            return

        selected = self._algo_menu.get()
        key = ALGO_KEY[selected]
        result = run_algorithm(key, processes, quantum=quantum)
        self._last_result = result

        self._all_results = {
            algo: run_algorithm(ALGO_KEY[algo], processes, quantum=quantum)
            for algo in ALGORITHMS
        }

        self._build_results_table(result)
        self._update_metrics(result)
        self._draw_gantt(result.gantt)

        if self._compare_menu.get() == "Round Robin (RR)":
            self._compare_quantum_entry.delete(0, "end")
            self._compare_quantum_entry.insert(0, str(quantum))
            self._compare_quantum_active = quantum
            self._apply_quantum_btn.configure(state="disabled")

        self._refresh_comparison()

    def _show_error(self, msg: str):
        self._error_label.configure(text=f"⚠  {msg}")

    def _clear_error(self):
        self._error_label.configure(text="")

    def _section(self, title: str, row: int) -> ctk.CTkFrame:
        card = ctk.CTkFrame(self.scroll, corner_radius=12)
        card.grid(row=row, column=0, sticky="ew", pady=(0, PAD))
        card.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            card, text=title,
            font=ctk.CTkFont(size=17, weight="bold"),
        ).grid(row=0, column=0, sticky="w", padx=PAD, pady=(PAD, 6))
        return card

if __name__ == "__main__":
    app = CPUSchedulerApp()
    app.mainloop()