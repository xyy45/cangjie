"""Exact server JSON display is presentation only, never object authorization."""
import json
from nexus.web.property_view import primitive_text
from tests.test_object_contracts import state


def test_object_evidence_has_lossless_nested_int64_display_text():
    low=-(1<<63);high=(1<<63)-1;fact=dict(args=[state(low)],actual_return=state(high),expected_value=state(low),actual_value=high)
    view=primitive_text(fact)
    assert view['args_text']==json.dumps(fact['args'],ensure_ascii=False,separators=(',',':'))
    assert str(high) in view['actual_return_text'] and str(low) in view['expected_value_text'] and view['actual_value_text']==str(high)
    assert fact['actual_return']==state(high) and 'actual_return_text' not in fact


def test_text_only_field_does_not_gain_a_fake_canonical_null_actual():
    value=dict(kind='public_field',value_state='TEXT_ONLY',actual_value=None,expected_value='中',actual_text='-bad\n+中')
    view=primitive_text(value);assert 'actual_value_text' not in view and view['actual_text']==value['actual_text'] and view['expected_value_text']=='"中"'
