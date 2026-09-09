"""
Headless smoke test: launches the real SegyQCApp under Xvfb, drives it
through load-file -> run QC -> switch tabs -> batch panel -> rules panel
-> compare, then closes. This is not a pytest test (needs a display via
xvfb-run) - it's a manual verification script exercising the actual
Tkinter app end-to-end rather than testing panels in isolation.
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

os.makedirs("data", exist_ok=True)
os.makedirs("outputs", exist_ok=True)

TEST_FILE = "data/gui_test.sgy"
if not os.path.exists(TEST_FILE):
    from segyqc.synth_generator import generate_synthetic_line
    generate_synthetic_line(out_path=TEST_FILE, n_shots=5, n_receivers=20)

from segyqc.gui.app import SegyQCApp

errors = []

def step(app):
    try:
        print("1. Loading file...")
        app.load_file(TEST_FILE)
        print("   format:", app.format_label.cget("text"))

        print("1b. Testing revision override...")
        app.revision_override_var.set("Rev 1 (2002)")
        app._refresh_format_label()
        assert "Rev 1 (2002)" in app.format_label.cget("text")
        assert "user override" in app.format_label.cget("text")
        app.revision_override_var.set("Auto-detected")
        app._refresh_format_label()
        assert "user override" not in app.format_label.cget("text")

        print("2. Running QC...")
        app.run_qc_on_current()
        app.after(1500, lambda: check_qc_done(app))
    except Exception as e:
        import traceback
        errors.append(f"step1/2: {traceback.format_exc()}")
        app.after(100, app.destroy)


def check_qc_done(app):
    try:
        print("   report:", app.current_report.critical_count(), "critical,",
              app.current_report.warning_count(), "warning")
        assert app.current_report is not None

        print("3. Switching tabs...")
        for i in range(len(app.notebook.tabs())):
            app.notebook.select(i)
            app.update()

        print("4. Testing rules panel get/set config...")
        cfg = app.rules_panel.get_config()
        cfg.spike_z_threshold = 3.0
        app.rules_panel.set_config(cfg)
        assert app.rules_panel.get_config().spike_z_threshold == 3.0

        print("5. Testing header panel (new fields)...")
        app.header_panel.load_file(TEST_FILE)
        rows = app.header_panel.tree.get_children()
        assert len(rows) > 0
        field_names = [app.header_panel.tree.item(r, "values")[0] for r in rows]
        for expected in ["EnergySourcePoint", "ShotPoint", "YearDataRecorded", "HourOfDay"]:
            assert expected in field_names, f"missing expected header field: {expected}"

        print("6. Testing trace viewer - display modes, gain, AGC, spectrum...")
        app.trace_viewer.count_var.set(5)
        for mode in ["wiggle", "VA", "wiggle+VA", "Variable Density"]:
            app.trace_viewer.mode_var.set(mode)
            app.trace_viewer.redraw()
        app.trace_viewer.gain_mode_var.set("Manual")
        app.trace_viewer.gain_value_var.set(3.0)
        app.trace_viewer.redraw()
        app.trace_viewer.gain_mode_var.set("AGC")
        app.trace_viewer.agc_window_var.set(150)
        app.trace_viewer.redraw()
        app.trace_viewer.show_spectrum_var.set(True)
        app.trace_viewer.redraw()
        assert app.trace_viewer.ax_spectrum is not None
        app.trace_viewer.show_spectrum_var.set(False)
        app.trace_viewer.redraw()

        print("7. Testing compare (before/after same file)...")
        app._set_compare_slot("before")
        app._set_compare_slot("after")
        app._run_compare()
        assert len(app.compare_tree.get_children()) > 0

        print("8. Testing export...")
        from segyqc.gui.export import export_csv, export_pdf
        export_csv(app.current_report, "outputs/gui_smoke_test.csv")
        export_pdf(app.current_report, "outputs/gui_smoke_test.pdf")
        assert os.path.exists("outputs/gui_smoke_test.csv")
        assert os.path.exists("outputs/gui_smoke_test.pdf")

        print("ALL STEPS PASSED")
    except Exception as e:
        import traceback
        errors.append(traceback.format_exc())
    finally:
        app.after(200, app.destroy)


app = SegyQCApp()
app.after(200, lambda: step(app))
app.after(15000, app.destroy)  # watchdog: force-close if something hangs
app.mainloop()

if errors:
    print("\n=== ERRORS ===")
    for e in errors:
        print(e)
    sys.exit(1)
else:
    print("\nSmoke test completed with no errors.")
