import sys, traceback
from src.qt_api import QApplication, QTimer

sys.excepthook = lambda *a: (traceback.print_exception(*a),)

import demo_heading_panel

def test():
    p = demo_heading_panel.win.panel
    results = []
    try:
        p._mode_btn_adv.click()
        p._mode_btn_simple.click()
        p._mode_btn_adv.click()
        results.append("PASS: mode switching")

        p._preset_cb.setCurrentIndex(0)
        assert not p._prefix_edit.isEnabled(), 'prefix should be locked'
        results.append("PASS: prefix locked in preset mode")
        
        assert p._levels_cb.isEnabled(), 'levels should stay unlocked'
        results.append("PASS: levels always unlocked")
        
        assert p._nn_texts_edit.isEnabled(), 'nn should stay unlocked'
        results.append("PASS: nn_texts always unlocked")
        
        assert p._toc_checkbox.isEnabled(), 'toc should be unlocked per SPEC'
        results.append("PASS: TOC checkbox always unlocked (SPEC compliant)")

        p._preset_cb.setCurrentIndex(p._preset_cb.count() - 1)
        assert p._prefix_edit.isEnabled(), 'prefix should be unlocked in custom'
        results.append("PASS: prefix unlocked in custom mode")

        p._adv_list.setCurrentRow(0)
        p._adv_list.setCurrentRow(1)
        p._adv_list.setCurrentRow(2)
        results.append("PASS: level switching without crash")

        assert p._ref_style_cb.itemData(0) == 'arabic', f'got {p._ref_style_cb.itemData(0)}'
        assert p._core_style_cb.itemData(1) == 'chinese_lower', f'got {p._core_style_cb.itemData(1)}'
        results.append("PASS: ComboBox data uses core_style keys")

        print("\n".join(results))
        print(f"\nALL {len(results)} TESTS PASSED")
    except Exception as e:
        print("\n".join(results))
        print(f"\nFAIL: {e}")
        traceback.print_exc()
    QApplication.quit()

QTimer.singleShot(800, test)
