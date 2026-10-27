from dados.economia import XP_PARA_SUBIR
from logica.dicas import CURVA_JOGAR_NO_8, CURVA_SUBIR_PARA_O_9, curva_do_plano, xp_ate
from logica.taticas import Plano


def test_xp_ate():
    # Nivel 2 -> 3
    assert xp_ate(2, 0, 3, XP_PARA_SUBIR) == 2
    assert xp_ate(2, 1, 3, XP_PARA_SUBIR) == 1
    assert xp_ate(2, 2, 3, XP_PARA_SUBIR) == 0

    # Nivel 2 -> 4
    assert xp_ate(2, 0, 4, XP_PARA_SUBIR) == 2 + 6
    assert xp_ate(2, 1, 4, XP_PARA_SUBIR) == 1 + 6
    assert xp_ate(2, 4, 4, XP_PARA_SUBIR) == 0 + 4

    # Nivel igual
    assert xp_ate(4, 10, 4, XP_PARA_SUBIR) == 0


def test_curva_do_plano_none():
    assert curva_do_plano(None) == CURVA_JOGAR_NO_8


def test_curva_do_plano_jogar_no_8():
    plano = Plano(
        estilo="Jogar no 8",
        nivel_alvo=8,
        tres_estrelas=[],
        nivel_final_medio=8.0,
        chegam_no_9=0.1,
        texto="",
    )
    assert curva_do_plano(plano) == CURVA_JOGAR_NO_8


def test_curva_do_plano_subir_para_o_9():
    plano = Plano(
        estilo="Subir para o 9",
        nivel_alvo=9,
        tres_estrelas=[],
        nivel_final_medio=9.0,
        chegam_no_9=0.9,
        texto="",
    )
    assert curva_do_plano(plano) == CURVA_SUBIR_PARA_O_9


def test_curva_do_plano_reroll_3():
    plano = Plano(
        estilo="Reroll",
        nivel_alvo=7,
        tres_estrelas=[],
        nivel_final_medio=7.5,
        chegam_no_9=0.0,
        texto="",
    )
    # CURVA_JOGAR_NO_8: [(2, 1, 4), (2, 5, 5), (3, 2, 6), (4, 1, 7), (4, 2, 8)]
    # nivel 7 reroll
    expected = [(2, 1, 4), (2, 5, 5), (3, 2, 6), (4, 1, 7)]
    assert curva_do_plano(plano) == expected
