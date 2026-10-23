"""Controle de pausa independente da fila de tarefas e da interface gráfica."""
class Pausa:
    def __init__(self):
        self.ativa = False

    def alternar(self, estado):
        if estado == 'jogando':
            self.ativa = not self.ativa
        return self.ativa

    def desenhar(self, app):
        if self.ativa:
            # Import local: o controle também pode ser testado sem SDL.
            import pygame
            sombra = pygame.Surface(app.canvas.get_size(), pygame.SRCALPHA)
            sombra.fill((0, 0, 0, 155))
            app.canvas.blit(sombra, (0, 0))
            app.texto('PAUSADO', 490, 390, 52)
