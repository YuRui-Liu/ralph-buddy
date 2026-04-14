import pytest
from agent.pet_attributes import PetAttributeManager

@pytest.fixture
def mgr():
    m = PetAttributeManager.__new__(PetAttributeManager)
    m.attrs = {
        'health': 80.0, 'mood': 75.0, 'energy': 85.0,
        'affection': 70.0, 'obedience': 45.0, 'snark': 65.0,
    }
    return m

def test_returns_string(mgr):
    result = mgr.build_self_awareness()
    assert isinstance(result, str)
    assert len(result) > 20

def test_no_numbers_in_output(mgr):
    result = mgr.build_self_awareness()
    assert '/100' not in result
    assert '健康值' not in result

def test_high_energy_high_mood(mgr):
    mgr.attrs['energy'] = 90.0
    mgr.attrs['mood'] = 85.0
    result = mgr.build_self_awareness()
    assert any(w in result for w in ['兴奋', '想玩', '想闹', '精神', '坐不住'])

def test_low_energy_low_mood(mgr):
    mgr.attrs['energy'] = 20.0
    mgr.attrs['mood'] = 25.0
    result = mgr.build_self_awareness()
    assert any(w in result for w in ['不想动', '不太想动', '趴着', '趴在', '累', '没劲'])

def test_high_affection_high_snark(mgr):
    mgr.attrs['affection'] = 85.0
    mgr.attrs['snark'] = 80.0
    result = mgr.build_self_awareness()
    assert any(w in result for w in ['吐槽', '调侃', '随意', '不怕'])

def test_low_affection_low_snark(mgr):
    mgr.attrs['affection'] = 25.0
    mgr.attrs['snark'] = 20.0
    result = mgr.build_self_awareness()
    assert any(w in result for w in ['拘谨', '客气', '还不太', '不太熟'])

def test_low_health_overlay(mgr):
    mgr.attrs['health'] = 25.0
    result = mgr.build_self_awareness()
    assert any(w in result for w in ['不舒服', '难受', '蔫'])

def test_obedience_high(mgr):
    mgr.attrs['obedience'] = 85.0
    result = mgr.build_self_awareness()
    assert any(w in result for w in ['听话', '配合', '积极'])

def test_obedience_low(mgr):
    mgr.attrs['obedience'] = 20.0
    result = mgr.build_self_awareness()
    assert any(w in result for w in ['自己的', '主意', '不一定', '任性'])
