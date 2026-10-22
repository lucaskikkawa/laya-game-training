"""Sons locais sintetizados com numpy; áudio indisponível não impede jogar."""
import numpy as np
import pygame


class Sons:
    def __init__(self):
        self.sons = {}
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(frequency=22050, size=-16, channels=2)
            frequencia, _, canais = pygame.mixer.get_init()
            for nome, hz, duracao in (("comida", 660, .12), ("morte", 140, .3), ("vitoria", 880, .4)):
                tempo = np.arange(int(frequencia * duracao)) / frequencia
                onda = (np.sin(2 * np.pi * hz * tempo) * np.exp(-tempo * 8) * 6000).astype(np.int16)
                if canais > 1:
                    onda = np.repeat(onda[:, None], canais, axis=1)
                self.sons[nome] = pygame.sndarray.make_sound(np.ascontiguousarray(onda))
        except pygame.error:
            pass

    def tocar(self, nome):
        if nome in self.sons:
            self.sons[nome].play()
