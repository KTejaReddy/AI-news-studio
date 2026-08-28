"""Production View — AI Production Orchestrator UI.

Provides a comprehensive dashboard for submitting, monitoring, and managing
production pipeline jobs. Integrates with the ProductionOrchestrator through
the MainWindow's ``production_orchestrator`` attribute.
"""

import logging
import threading
import tkinter as tk
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Dict, List, Optional

import customtkinter as ctk

from app.theme import Theme
from core.production.production_job import ProductionJob, ProductionJobConfig
from core.production.production_state import PipelineStage, ProductionState

if TYPE_CHECKING:
    from app.gui import MainWindow


class PipelineStageCard(ctk.CTkFrame):
    """Visual card representing a single pipeline stage status."""

    # State colour mapping
    STATE_COLORS = {
        "pending": ("#4b5563", "#374151"),
        "running": ("#1d4ed8", "#1e40af"),
        "completed": ("#065f46", "#064e3b"),
        "failed": ("#991b1b", "#7f1d1d"),
        "skipped": ("#374151", "#1f2937"),
        "cached": ("#4d7c0f", "#3f6212"),
    }

    STATE_ICONS = {
        "pending": "○",
        "running": "⟳",
        "completed": "✓",
        "failed": "✗",
        "skipped": "→",
        "cached": "⚡",
    }

    def __init__(self, parent: ctk.CTkFrame, stage: PipelineStage) -> None:
        """Initialize PipelineStageCard.

        Args:
            parent: Parent frame widget.
            stage: The PipelineStage this card represents.
        """
        super().__init__(
            parent,
            height=52,
            corner_radius=8,
            fg_color=self.STATE_COLORS["pending"][0],
            border_width=1,
            border_color=Theme.BORDER_COLOR,
        )
        self.stage = stage
        self.pack_propagate(False)

        # Icon + label layout
        self.icon_label = ctk.CTkLabel(
            self,
            text=self.STATE_ICONS["pending"],
            font=Theme.get_font(18, "bold"),
            text_color=Theme.TEXT_SECONDARY,
            width=36,
        )
        self.icon_label.pack(side="left", padx=(10, 4), pady=6)

        text_frame = ctk.CTkFrame(self, fg_color="transparent")
        text_frame.pack(side="left", fill="both", expand=True, pady=6)

        self.name_label = ctk.CTkLabel(
            text_frame,
            text=PipelineStage.label(stage),
            font=Theme.get_font(12, "bold"),
            text_color=Theme.TEXT_PRIMARY,
            anchor="w",
        )
        self.name_label.pack(side="top", fill="x", padx=4)

        self.detail_label = ctk.CTkLabel(
            text_frame,
            text="Waiting...",
            font=Theme.get_font(10, "normal"),
            text_color=Theme.TEXT_SECONDARY,
            anchor="w",
        )
        self.detail_label.pack(side="top", fill="x", padx=4)

        self.time_label = ctk.CTkLabel(
            self,
            text="",
            font=Theme.get_font(10, "normal"),
            text_color=Theme.TEXT_SECONDARY,
            width=60,
        )
        self.time_label.pack(side="right", padx=10, pady=6)

    def update_state(self, status: str, detail: str = "", duration: float = 0.0) -> None:
        """Update the card's visual state.

        Args:
            status: Stage status string (pending/running/completed/failed/skipped).
            detail: Short detail message.
            duration: Stage elapsed time in seconds.
        """
        colors = self.STATE_COLORS.get(status, self.STATE_COLORS["pending"])
        icon = self.STATE_ICONS.get(status, "○")
        self.configure(fg_color=colors[0])
        self.icon_label.configure(text=icon)
        self.detail_label.configure(text=detail or status.capitalize())
        if duration > 0:
            self.time_label.configure(text=f"{duration:.1f}s")


class JobQueueRow(ctk.CTkFrame):
    """Single row representing a job in the queue list."""

    def __init__(
        self,
        parent: ctk.CTkFrame,
        job: ProductionJob,
        on_cancel: Optional[callable] = None,
    ) -> None:
        """Initialize JobQueueRow.

        Args:
            parent: Parent container.
            job: The ProductionJob this row represents.
            on_cancel: Callback invoked when user clicks Cancel.
        """
        super().__init__(
            parent,
            corner_radius=6,
            fg_color=Theme.BG_CARD,
            border_width=1,
            border_color=Theme.BORDER_COLOR,
        )
        self.job = job
        self.on_cancel = on_cancel

        # Status indicator dot
        status_colors = {
            "idle": "#6b7280",
            "queued": "#f59e0b",
            "running": "#3b82f6",
            "completed": "#10b981",
            "failed": "#ef4444",
            "cancelled": "#6b7280",
            "retrying": "#f97316",
        }
        color = status_colors.get(job.status, "#6b7280")
        self.dot = ctk.CTkLabel(
            self,
            text="●",
            font=Theme.get_font(14, "bold"),
            text_color=color,
            width=20,
        )
        self.dot.pack(side="left", padx=(10, 4), pady=8)

        # Job ID + project
        info_frame = ctk.CTkFrame(self, fg_color="transparent")
        info_frame.pack(side="left", fill="both", expand=True, pady=6)

        self.id_label = ctk.CTkLabel(
            info_frame,
            text=f"Job {job.job_id[:8]}",
            font=Theme.get_font(12, "bold"),
            text_color=Theme.TEXT_PRIMARY,
            anchor="w",
        )
        self.id_label.pack(side="top", fill="x", padx=4)

        proj_id = job.config.project_id[:16]
        self.proj_label = ctk.CTkLabel(
            info_frame,
            text=f"Project: {proj_id}...",
            font=Theme.get_font(10, "normal"),
            text_color=Theme.TEXT_SECONDARY,
            anchor="w",
        )
        self.proj_label.pack(side="top", fill="x", padx=4)

        # Progress bar
        self.progress_bar = ctk.CTkProgressBar(
            self,
            width=100,
            height=8,
            corner_radius=4,
            fg_color=Theme.BG_MAIN,
            progress_color=color,
        )
        self.progress_bar.set(job.progress.overall_progress)
        self.progress_bar.pack(side="left", padx=(0, 10), pady=8)

        # Status + cancel button
        right = ctk.CTkFrame(self, fg_color="transparent")
        right.pack(side="right", padx=(0, 10))

        self.status_label = ctk.CTkLabel(
            right,
            text=job.status.upper(),
            font=Theme.get_font(10, "bold"),
            text_color=color,
        )
        self.status_label.pack(side="top", pady=(6, 0))

        if not job.is_terminal:
            cancel_btn = ctk.CTkButton(
                right,
                text="Cancel",
                width=60,
                height=22,
                corner_radius=6,
                font=Theme.get_font(10, "bold"),
                fg_color="#7f1d1d",
                hover_color="#991b1b",
                command=self._handle_cancel,
            )
            cancel_btn.pack(side="top", pady=(2, 6))

    def _handle_cancel(self) -> None:
        """Invoke the cancel callback for this job."""
        if self.on_cancel:
            self.on_cancel(self.job.job_id)

    def refresh(self, job: ProductionJob) -> None:
        """Update the row's visual state from the latest job data.

        Args:
            job: Updated ProductionJob.
        """
        self.job = job
        status_colors = {
            "idle": "#6b7280",
            "queued": "#f59e0b",
            "running": "#3b82f6",
            "completed": "#10b981",
            "failed": "#ef4444",
            "cancelled": "#6b7280",
            "retrying": "#f97316",
        }
        color = status_colors.get(job.status, "#6b7280")
        self.dot.configure(text_color=color)
        self.status_label.configure(text=job.status.upper(), text_color=color)
        self.progress_bar.set(job.progress.overall_progress)
        self.progress_bar.configure(progress_color=color)


class ProductionView(ctk.CTkFrame):
    """Full-featured production orchestrator dashboard.

    Features:
    - Job submission form (project selector, presenter/voice, quality)
    - Live pipeline stage tracker with per-stage status cards
    - Job queue list with cancel buttons
    - Live log stream panel
    - System stats (active jobs, queue depth, history count)
    """

    POLL_INTERVAL_MS = 500  # UI refresh rate

    def __init__(self, parent: ctk.CTkFrame, main_window: "MainWindow") -> None:
        """Initialize ProductionView.

        Args:
            parent: Parent viewport container.
            main_window: Reference to the MainWindow instance.
        """
        super().__init__(parent, fg_color=Theme.BG_MAIN, corner_radius=0)
        self.main_window = main_window
        self._logger = logging.getLogger(self.__class__.__name__)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Active job being monitored in the pipeline panel
        self._monitored_job: Optional[ProductionJob] = None
        self._stage_cards: Dict[PipelineStage, PipelineStageCard] = {}
        self._queue_rows: Dict[str, JobQueueRow] = {}
        self._polling = False

        self._build_ui()

    # ── UI Construction ──────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        """Construct all UI panels."""
        # Main content grid: left panel (form + queue) | right panel (pipeline + log)
        self.content_frame = ctk.CTkFrame(self, fg_color=Theme.BG_MAIN, corner_radius=0)
        self.content_frame.grid(row=0, column=0, sticky="nsew", padx=0, pady=0)
        self.content_frame.grid_columnconfigure(0, weight=1, minsize=340)
        self.content_frame.grid_columnconfigure(1, weight=2)
        self.content_frame.grid_rowconfigure(0, weight=1)

        self._build_left_panel()
        self._build_right_panel()

    def _build_left_panel(self) -> None:
        """Build the left panel containing submission form and queue."""
        left = ctk.CTkFrame(self.content_frame, fg_color=Theme.BG_SIDEBAR, corner_radius=0)
        left.grid(row=0, column=0, sticky="nsew")
        left.grid_rowconfigure(2, weight=1)
        left.grid_columnconfigure(0, weight=1)

        # Header
        header = ctk.CTkLabel(
            left,
            text="🚀 Production Queue",
            font=Theme.get_font(16, "bold"),
            text_color=Theme.TEXT_PRIMARY,
            anchor="w",
        )
        header.grid(row=0, column=0, padx=20, pady=(20, 8), sticky="w")

        # Submission form
        self._build_submission_form(left)

        # Queue list
        queue_header = ctk.CTkLabel(
            left,
            text="Active & Queued Jobs",
            font=Theme.get_font(13, "bold"),
            text_color=Theme.TEXT_SECONDARY,
            anchor="w",
        )
        queue_header.grid(row=2, column=0, padx=20, pady=(16, 4), sticky="w")

        queue_scroll = ctk.CTkScrollableFrame(
            left,
            fg_color=Theme.BG_MAIN,
            corner_radius=8,
            border_width=1,
            border_color=Theme.BORDER_COLOR,
        )
        queue_scroll.grid(row=3, column=0, sticky="nsew", padx=12, pady=(0, 16))
        queue_scroll.grid_columnconfigure(0, weight=1)
        left.grid_rowconfigure(3, weight=1)
        self._queue_container = queue_scroll

        # Stats bar at bottom
        self._build_stats_bar(left)

    def _build_submission_form(self, parent: ctk.CTkFrame) -> None:
        """Build the job submission form.

        Args:
            parent: Parent frame to place the form into.
        """
        form = ctk.CTkFrame(
            parent,
            fg_color=Theme.BG_CARD,
            corner_radius=10,
            border_width=1,
            border_color=Theme.BORDER_COLOR,
        )
        form.grid(row=1, column=0, padx=12, pady=(0, 4), sticky="ew")
        form.grid_columnconfigure(0, weight=1)

        form_title = ctk.CTkLabel(
            form,
            text="New Production Job",
            font=Theme.get_font(13, "bold"),
            text_color=Theme.TEXT_PRIMARY,
            anchor="w",
        )
        form_title.grid(row=0, column=0, padx=14, pady=(12, 6), sticky="w")

        # Script text
        script_label = ctk.CTkLabel(form, text="Script:", font=Theme.get_font(11), text_color=Theme.TEXT_SECONDARY, anchor="w")
        script_label.grid(row=1, column=0, padx=14, pady=(0, 2), sticky="w")

        self._script_box = ctk.CTkTextbox(
            form,
            height=80,
            corner_radius=6,
            font=Theme.get_font(11),
            fg_color=Theme.BG_MAIN,
            border_width=1,
            border_color=Theme.BORDER_COLOR,
        )
        self._script_box.grid(row=2, column=0, padx=14, pady=(0, 8), sticky="ew")
        self._script_box.insert("1.0", "Enter your news script here...")

        # Presenter ID
        self._presenter_var = tk.StringVar(value="default")
        pid_row = ctk.CTkFrame(form, fg_color="transparent")
        pid_row.grid(row=3, column=0, padx=14, sticky="ew")
        pid_row.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(pid_row, text="Presenter:", font=Theme.get_font(11), text_color=Theme.TEXT_SECONDARY).grid(row=0, column=0, padx=(0, 8), sticky="w")
        ctk.CTkEntry(pid_row, textvariable=self._presenter_var, height=28, corner_radius=6, fg_color=Theme.BG_MAIN, border_color=Theme.BORDER_COLOR).grid(row=0, column=1, sticky="ew")

        # Voice Profile dropdown (populated from VoiceEngine registry)
        vid_row = ctk.CTkFrame(form, fg_color="transparent")
        vid_row.grid(row=4, column=0, padx=14, pady=(6, 0), sticky="ew")
        vid_row.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(vid_row, text="Voice Profile:", font=Theme.get_font(11), text_color=Theme.TEXT_SECONDARY).grid(row=0, column=0, padx=(0, 8), sticky="w")
        self._voice_dropdown = ctk.CTkOptionMenu(
            vid_row,
            values=["(no voice profiles)"],
            height=28,
            corner_radius=6,
            fg_color=Theme.BG_MAIN,
            button_color=Theme.ACCENT,
            button_hover_color=Theme.ACCENT_HOVER if hasattr(Theme, "ACCENT_HOVER") else Theme.ACCENT,
            text_color=Theme.TEXT_PRIMARY,
            dropdown_fg_color=Theme.BG_CARD,
            font=Theme.get_font(11),
        )
        self._voice_dropdown.grid(row=0, column=1, sticky="ew")
        # Internal mapping: display label -> profile_id
        self._voice_profile_map: Dict[str, str] = {}

        # Quality + Aspect ratio
        opts_row = ctk.CTkFrame(form, fg_color="transparent")
        opts_row.grid(row=5, column=0, padx=14, pady=(6, 0), sticky="ew")
        opts_row.grid_columnconfigure(0, weight=1)
        opts_row.grid_columnconfigure(1, weight=1)

        self._quality_var = tk.StringVar(value="High")
        ctk.CTkLabel(opts_row, text="Quality:", font=Theme.get_font(11), text_color=Theme.TEXT_SECONDARY).grid(row=0, column=0, padx=(0, 4), sticky="w")
        ctk.CTkComboBox(
            opts_row,
            values=["Low", "Medium", "High"],
            variable=self._quality_var,
            height=28,
            corner_radius=6,
            fg_color=Theme.BG_MAIN,
            border_color=Theme.BORDER_COLOR,
            font=Theme.get_font(11),
        ).grid(row=0, column=0, pady=(18, 0), sticky="ew", padx=(0, 4))

        self._ratio_var = tk.StringVar(value="16:9")
        ctk.CTkLabel(opts_row, text="Aspect:", font=Theme.get_font(11), text_color=Theme.TEXT_SECONDARY).grid(row=0, column=1, padx=(4, 0), sticky="w")
        ctk.CTkComboBox(
            opts_row,
            values=["16:9", "9:16", "1:1", "4:3"],
            variable=self._ratio_var,
            height=28,
            corner_radius=6,
            fg_color=Theme.BG_MAIN,
            border_color=Theme.BORDER_COLOR,
            font=Theme.get_font(11),
        ).grid(row=0, column=1, pady=(18, 0), sticky="ew", padx=(4, 0))

        # Cache toggle
        self._cache_var = tk.BooleanVar(value=True)
        cache_row = ctk.CTkFrame(form, fg_color="transparent")
        cache_row.grid(row=6, column=0, padx=14, pady=(8, 0), sticky="w")
        ctk.CTkCheckBox(
            cache_row,
            text="Use cache (skip already-generated stages)",
            variable=self._cache_var,
            font=Theme.get_font(11),
            text_color=Theme.TEXT_SECONDARY,
            checkbox_width=16,
            checkbox_height=16,
            corner_radius=4,
        ).pack(side="left")

        # Preview toggle
        self._preview_var = tk.BooleanVar(value=True)
        prev_row = ctk.CTkFrame(form, fg_color="transparent")
        prev_row.grid(row=7, column=0, padx=14, pady=(4, 0), sticky="w")
        ctk.CTkCheckBox(
            prev_row,
            text="Generate preview before export",
            variable=self._preview_var,
            font=Theme.get_font(11),
            text_color=Theme.TEXT_SECONDARY,
            checkbox_width=16,
            checkbox_height=16,
            corner_radius=4,
        ).pack(side="left")

        # Submit button
        self._submit_btn = ctk.CTkButton(
            form,
            text="▶ Start Production",
            font=Theme.get_font(13, "bold"),
            height=36,
            corner_radius=8,
            fg_color=Theme.ACCENT,
            hover_color=Theme.ACCENT_HOVER if hasattr(Theme, "ACCENT_HOVER") else Theme.ACCENT,
            text_color=Theme.TEXT_ON_ACCENT,
            command=self._on_submit,
        )
        self._submit_btn.grid(row=8, column=0, padx=14, pady=(10, 14), sticky="ew")

    def _build_stats_bar(self, parent: ctk.CTkFrame) -> None:
        """Build system statistics labels at the bottom of the left panel.

        Args:
            parent: Parent frame to attach the stats bar.
        """
        stats = ctk.CTkFrame(parent, fg_color=Theme.BG_CARD, corner_radius=8, border_width=1, border_color=Theme.BORDER_COLOR)
        stats.grid(row=4, column=0, padx=12, pady=(0, 16), sticky="ew")
        stats.grid_columnconfigure(0, weight=1)
        stats.grid_columnconfigure(1, weight=1)
        stats.grid_columnconfigure(2, weight=1)

        self._stat_active = self._make_stat_label(stats, "Active", "0", 0)
        self._stat_queued = self._make_stat_label(stats, "Queued", "0", 1)
        self._stat_history = self._make_stat_label(stats, "History", "0", 2)

    def _make_stat_label(
        self,
        parent: ctk.CTkFrame,
        title: str,
        value: str,
        col: int,
    ) -> ctk.CTkLabel:
        """Create a single statistic value label in the stats bar.

        Args:
            parent: Parent frame.
            title: Statistic title text.
            value: Initial value string.
            col: Grid column index.

        Returns:
            The value CTkLabel for future updates.
        """
        container = ctk.CTkFrame(parent, fg_color="transparent")
        container.grid(row=0, column=col, padx=12, pady=10, sticky="nsew")

        ctk.CTkLabel(
            container,
            text=title,
            font=Theme.get_font(10, "normal"),
            text_color=Theme.TEXT_SECONDARY,
        ).pack()

        val_label = ctk.CTkLabel(
            container,
            text=value,
            font=Theme.get_font(20, "bold"),
            text_color=Theme.TEXT_PRIMARY,
        )
        val_label.pack()
        return val_label

    def _build_right_panel(self) -> None:
        """Build the right panel with pipeline stages and live log."""
        right = ctk.CTkFrame(self.content_frame, fg_color=Theme.BG_MAIN, corner_radius=0)
        right.grid(row=0, column=1, sticky="nsew")
        right.grid_rowconfigure(1, weight=1)
        right.grid_rowconfigure(3, weight=1)
        right.grid_columnconfigure(0, weight=1)

        # Pipeline stages header
        pipeline_header_row = ctk.CTkFrame(right, fg_color="transparent")
        pipeline_header_row.grid(row=0, column=0, padx=20, pady=(20, 8), sticky="ew")
        pipeline_header_row.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            pipeline_header_row,
            text="🎬 Pipeline Status",
            font=Theme.get_font(16, "bold"),
            text_color=Theme.TEXT_PRIMARY,
            anchor="w",
        ).grid(row=0, column=0, sticky="w")

        self._overall_label = ctk.CTkLabel(
            pipeline_header_row,
            text="No active job",
            font=Theme.get_font(11),
            text_color=Theme.TEXT_SECONDARY,
        )
        self._overall_label.grid(row=0, column=1, sticky="e")

        # Overall progress bar
        self._overall_progress = ctk.CTkProgressBar(
            right,
            height=10,
            corner_radius=5,
            fg_color=Theme.BG_CARD,
            progress_color=Theme.ACCENT,
        )
        self._overall_progress.set(0.0)
        self._overall_progress.grid(row=0, column=0, padx=20, pady=(54, 0), sticky="ew")

        # Stage cards scroll area
        stage_scroll = ctk.CTkScrollableFrame(
            right,
            fg_color=Theme.BG_CARD,
            corner_radius=10,
            border_width=1,
            border_color=Theme.BORDER_COLOR,
        )
        stage_scroll.grid(row=1, column=0, padx=20, pady=(10, 0), sticky="nsew")
        stage_scroll.grid_columnconfigure(0, weight=1)
        self._stage_scroll = stage_scroll

        # Build one card per stage
        for stage in PipelineStage.ordered():
            card = PipelineStageCard(stage_scroll, stage)
            card.pack(fill="x", padx=8, pady=3)
            self._stage_cards[stage] = card

        # Log panel
        log_header = ctk.CTkLabel(
            right,
            text="📋 Live Production Log",
            font=Theme.get_font(13, "bold"),
            text_color=Theme.TEXT_SECONDARY,
            anchor="w",
        )
        log_header.grid(row=2, column=0, padx=20, pady=(16, 4), sticky="w")

        self._log_box = ctk.CTkTextbox(
            right,
            corner_radius=8,
            font=("Courier New", 10),
            fg_color=("#111827", "#030712"),
            text_color=("#d1fae5", "#d1fae5"),
            border_width=1,
            border_color=Theme.BORDER_COLOR,
            state="disabled",
        )
        self._log_box.grid(row=3, column=0, padx=20, pady=(0, 20), sticky="nsew")

    # ── Event Handlers ────────────────────────────────────────────────────────

    def _on_submit(self) -> None:
        """Validate the form and submit a new production job."""
        script = self._script_box.get("1.0", "end").strip()
        if not script or script == "Enter your news script here...":
            self._append_log("⚠ Please enter a script before starting production.", level="WARNING")
            return

        project = self.main_window.current_project
        if not project:
            self._append_log("⚠ No active project selected. Go to Projects and activate one.", level="WARNING")
            return

        try:
            voice_id = self._resolve_voice_id()
        except ValueError as exc:
            self._append_log(f"⚠ {exc}", level="WARNING")
            return

        config = ProductionJobConfig(
            project_id=project.id,
            script=script,
            presenter_id=self._presenter_var.get().strip() or "default",
            voice_id=voice_id,
            aspect_ratio=self._ratio_var.get(),
            quality=self._quality_var.get(),
            generate_preview=self._preview_var.get(),
            use_cache=self._cache_var.get(),
        )

        orchestrator = self.main_window.production_orchestrator
        job = orchestrator.produce(
            config=config,
            on_progress=self._on_job_progress,
        )

        self._monitored_job = job
        self._append_log(f"✓ Production job {job.job_id[:8]} submitted for project '{project.name}'.")
        self._refresh_queue()

    def _on_job_progress(self, job: ProductionJob) -> None:
        """Thread-safe callback for pipeline progress events.

        Args:
            job: The updated ProductionJob.
        """
        # Schedule UI update on the main thread
        self.after(0, lambda: self._apply_job_update(job))

    def _apply_job_update(self, job: ProductionJob) -> None:
        """Apply live job progress updates to the UI.

        Args:
            job: Updated ProductionJob.
        """
        # Update monitored job reference
        if self._monitored_job and self._monitored_job.job_id == job.job_id:
            self._monitored_job = job
            self._refresh_pipeline_panel(job)

        self._refresh_queue()
        self._refresh_stats()

    def _on_cancel_job(self, job_id: str) -> None:
        """Handle cancel button press for a queued/running job.

        Args:
            job_id: Job UUID to cancel.
        """
        self.main_window.production_orchestrator.cancel(job_id)
        self._append_log(f"→ Cancellation requested for job {job_id[:8]}.", level="WARNING")
        self._refresh_queue()

    # ── Panel Refresh Methods ─────────────────────────────────────────────────

    def _refresh_pipeline_panel(self, job: ProductionJob) -> None:
        """Update the pipeline stage cards from the job's stage results.

        Args:
            job: The active ProductionJob.
        """
        progress = job.progress
        self._overall_progress.set(progress.overall_progress)

        state_color = {
            ProductionState.RUNNING: "#3b82f6",
            ProductionState.COMPLETED: "#10b981",
            ProductionState.FAILED: "#ef4444",
            ProductionState.CANCELLED: "#6b7280",
        }.get(progress.state, "#6b7280")

        pct = int(progress.overall_progress * 100)
        stage_label = PipelineStage.label(progress.current_stage) if progress.current_stage else "—"
        self._overall_label.configure(
            text=f"{pct}% — {stage_label}",
            text_color=state_color,
        )
        self._overall_progress.configure(progress_color=state_color)

        # Update individual stage cards
        for stage in PipelineStage.ordered():
            card = self._stage_cards.get(stage)
            if not card:
                continue
            result = progress.get_stage_result(stage)
            if result:
                detail = ""
                if result.was_cached:
                    detail = "Cached ⚡"
                elif result.error_message:
                    detail = result.error_message[:40]
                elif result.output_data:
                    # Show first key/value pair as quick summary
                    k, v = next(iter(result.output_data.items()))
                    detail = f"{k}: {v}"
                card.update_state(
                    status="cached" if result.was_cached and result.status == "completed" else result.status,
                    detail=detail,
                    duration=result.duration_seconds,
                )
            elif progress.current_stage == stage:
                card.update_state("running", "In progress...")
            else:
                card.update_state("pending", "Waiting...")

        # Append log entries from the job's log file if available
        self._sync_job_logs(job)

    def _refresh_queue(self) -> None:
        """Rebuild the queue row list from the orchestrator's current state."""
        orchestrator = self.main_window.production_orchestrator
        jobs = orchestrator.get_queue()

        # Clear existing rows
        for widget in self._queue_container.winfo_children():
            widget.destroy()
        self._queue_rows.clear()

        if not jobs:
            ctk.CTkLabel(
                self._queue_container,
                text="No jobs queued.",
                font=Theme.get_font(11),
                text_color=Theme.TEXT_SECONDARY,
            ).pack(pady=20)
            return

        for job in reversed(jobs):
            row = JobQueueRow(
                self._queue_container,
                job,
                on_cancel=self._on_cancel_job,
            )
            row.pack(fill="x", padx=4, pady=3)
            self._queue_rows[job.job_id] = row

    def _refresh_stats(self) -> None:
        """Update the statistics labels in the left panel footer."""
        orchestrator = self.main_window.production_orchestrator
        active = len(orchestrator.get_active_jobs())
        all_jobs = orchestrator.get_queue()
        queued = len([j for j in all_jobs if j.status == "queued"])
        history = len(orchestrator.get_history(limit=9999))

        self._stat_active.configure(text=str(active))
        self._stat_queued.configure(text=str(queued))
        self._stat_history.configure(text=str(history))

    def _sync_job_logs(self, job: ProductionJob) -> None:
        """Pull log entries from the job's production logger and display them.

        Args:
            job: The active ProductionJob to read logs from.
        """
        from core.production.production_logger import ProductionLogger
        import json

        log_dir = (
            self.main_window.config_mgr.workspace_dir
            / "projects"
            / job.config.project_id
            / "logs"
        )
        log_file = log_dir / f"production_{job.job_id}.jsonl"

        if not log_file.exists():
            return

        try:
            with open(log_file, "r", encoding="utf-8") as f:
                entries = [json.loads(line) for line in f if line.strip()]

            # Only update if content has changed
            target_count = len(entries)
            existing_count = getattr(self, "_log_entry_count", 0)
            if target_count <= existing_count:
                return

            for entry in entries[existing_count:]:
                ts = entry.get("timestamp", "")[:19].replace("T", " ")
                lvl = entry.get("level", "INFO")
                stage = entry.get("stage", "")
                msg = entry.get("message", "")
                self._append_log(f"[{ts}] [{stage}] {msg}", level=lvl)

            self._log_entry_count = target_count
        except Exception:
            pass

    def _append_log(self, message: str, level: str = "INFO") -> None:
        """Append a message line to the live log textbox.

        Args:
            message: Message text to display.
            level: Severity level (INFO/WARNING/ERROR).
        """
        color_map = {
            "INFO": "#d1fae5",
            "WARNING": "#fef3c7",
            "ERROR": "#fecaca",
            "DEBUG": "#94a3b8",
        }
        self._log_box.configure(state="normal")
        self._log_box.insert("end", message + "\n")
        self._log_box.configure(state="disabled")
        self._log_box.see("end")

    def _refresh_voice_dropdown(self) -> None:
        """Populate the voice dropdown from the VoiceEngine profile registry."""
        engine = getattr(self.main_window, "voice_engine", None)
        if not engine:
            return

        profiles = engine.list_profiles()
        self._voice_profile_map.clear()

        if not profiles:
            self._voice_dropdown.configure(values=["(no voice profiles)"])
            self._voice_dropdown.set("(no voice profiles)")
            return

        labels = []
        for p in profiles:
            label = f"{p.name} [{p.profile_id[:8]}]"
            labels.append(label)
            self._voice_profile_map[label] = p.profile_id

        self._voice_dropdown.configure(values=labels)
        self._voice_dropdown.set(labels[0])

    def _resolve_voice_id(self) -> str:
        """Return the profile_id matching the currently selected dropdown entry.

        Falls back to the first available profile, or raises a descriptive
        error shown to the user if no profiles exist at all.

        Returns:
            The voice profile_id string to pass to the orchestrator.

        Raises:
            ValueError: When no voice profiles exist.
        """
        selected_label = self._voice_dropdown.get()
        profile_id = self._voice_profile_map.get(selected_label)

        if profile_id:
            return profile_id

        # Dropdown shows stale "(no voice profiles)" — try to refresh
        engine = getattr(self.main_window, "voice_engine", None)
        if engine:
            profiles = engine.list_profiles()
            if profiles:
                self._logger.warning(
                    "Voice dropdown was stale; using first available profile."
                )
                return profiles[0].profile_id

        raise ValueError(
            "No voice profiles found.\n\n"
            "Please go to the Voices tab and train at least one voice profile before starting production."
        )

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def on_show(self) -> None:
        """Called by the main window router when this view is activated."""
        self._refresh_voice_dropdown()
        self._refresh_queue()
        self._refresh_stats()
        if self._monitored_job:
            self._refresh_pipeline_panel(self._monitored_job)
        self._log_entry_count = 0
