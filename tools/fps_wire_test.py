import argparse
import math
import sys
import time

import pygame


def run(seconds=30, target_fps=120):
    pygame.init()
    pygame.display.set_caption("SystemGauges FPS Wire Test")
    screen = pygame.display.set_mode((960, 540), pygame.DOUBLEBUF)
    clock = pygame.time.Clock()
    font = pygame.font.SysFont("Segoe UI", 28)
    small_font = pygame.font.SysFont("Segoe UI", 18)
    start = time.time()
    frames = 0

    try:
        while True:
            now = time.time()
            elapsed = now - start
            if seconds > 0 and elapsed >= seconds:
                break

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return 0
                if event.type == pygame.KEYDOWN and event.key in (pygame.K_ESCAPE, pygame.K_q):
                    return 0

            frames += 1
            fps = clock.get_fps()
            phase = elapsed * 2.7
            x = int((math.sin(phase) * 0.42 + 0.5) * screen.get_width())
            y = int((math.cos(phase * 1.3) * 0.35 + 0.5) * screen.get_height())

            screen.fill((5, 8, 14))
            pygame.draw.circle(screen, (0, 255, 160), (x, y), 34)
            pygame.draw.circle(screen, (30, 144, 255), (screen.get_width() - x, screen.get_height() - y), 22)
            pygame.draw.line(screen, (255, 210, 80), (80, screen.get_height() - 80), (x, y), 3)

            title = font.render(f"FPS Wire Test  {fps:5.1f} FPS", True, (235, 250, 255))
            subtitle = small_font.render(
                "Run SystemGauges beside this window; its FPS gauge should identify this process.",
                True,
                (150, 190, 210),
            )
            screen.blit(title, (28, 24))
            screen.blit(subtitle, (30, 62))

            pygame.display.flip()
            clock.tick(target_fps)
    finally:
        pygame.quit()
    return 0


def main():
    parser = argparse.ArgumentParser(description="Render a steady window for SystemGauges FPS capture testing.")
    parser.add_argument("--seconds", type=float, default=30, help="Seconds to run; use 0 to run until closed.")
    parser.add_argument("--fps", type=int, default=120, help="Target render FPS.")
    args = parser.parse_args()
    return run(seconds=args.seconds, target_fps=args.fps)


if __name__ == "__main__":
    sys.exit(main())
