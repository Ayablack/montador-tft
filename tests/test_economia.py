from dados.economia import juros, ouro_da_sequencia


def test_juros():
    assert juros(0) == 0
    assert juros(9) == 0
    assert juros(10) == 1
    assert juros(15) == 1
    assert juros(20) == 2
    assert juros(50) == 5
    assert juros(60) == 5
    assert juros(-10) == 0


def test_ouro_da_sequencia():
    assert ouro_da_sequencia(1) == 0
    assert ouro_da_sequencia(2) == 0
    assert ouro_da_sequencia(3) == 1
    assert ouro_da_sequencia(4) == 1
    assert ouro_da_sequencia(5) == 2
    assert ouro_da_sequencia(6) == 3
    assert ouro_da_sequencia(7) == 3
    assert ouro_da_sequencia(10) == 3
