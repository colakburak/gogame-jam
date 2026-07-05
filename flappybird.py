#! /usr/bin/env python3

"""Flappy Bird, implemented using Pygame."""

import math
import os
from random import randint
from collections import deque

import pygame
from pygame.locals import *


FPS = 60
ANIMATION_SPEED = 0.18  # pixels per millisecond
WIN_WIDTH = 284 * 2     # BG image size: 284x512 px; tiled twice
WIN_HEIGHT = 512

PIPE_RISE_SPEED = 0.4   # px/ms when space held
PIPE_SINK_SPEED = 0.2   # px/ms natural fall


class Bird(pygame.sprite.Sprite):
    """Represents the bird controlled by the player.

    The bird is the 'hero' of this game.  The player can make it climb
    (ascend quickly), otherwise it sinks (descends more slowly).  It must
    pass through the space in between pipes (for every pipe passed, one
    point is scored); if it crashes into a pipe, the game ends.

    Attributes:
    x: The bird's X coordinate.
    y: The bird's Y coordinate.
    msec_to_climb: The number of milliseconds left to climb, where a
        complete climb lasts Bird.CLIMB_DURATION milliseconds.

    Constants:
    WIDTH: The width, in pixels, of the bird's image.
    HEIGHT: The height, in pixels, of the bird's image.
    SINK_SPEED: With which speed, in pixels per millisecond, the bird
        descends in one second while not climbing.
    CLIMB_SPEED: With which speed, in pixels per millisecond, the bird
        ascends in one second while climbing, on average.  See also the
        Bird.update docstring.
    CLIMB_DURATION: The number of milliseconds it takes the bird to
        execute a complete climb.
    """

    WIDTH = HEIGHT = 32
    SINK_SPEED = 0.18
    CLIMB_SPEED = 0.3
    CLIMB_DURATION = 333.3

    def __init__(self, x, y, msec_to_climb, images):
        """Initialise a new Bird instance.

        Arguments:
        x: The bird's initial X coordinate.
        y: The bird's initial Y coordinate.
        msec_to_climb: The number of milliseconds left to climb, where a
            complete climb lasts Bird.CLIMB_DURATION milliseconds.  Use
            this if you want the bird to make a (small?) climb at the
            very beginning of the game.
        images: A tuple containing the images used by this bird.  It
            must contain the following images, in the following order:
                0. image of the bird with its wing pointing upward
                1. image of the bird with its wing pointing downward
        """
        super(Bird, self).__init__()
        self.x, self.y = x, y
        self.msec_to_climb = msec_to_climb
        self._img_wingup, self._img_wingdown = images
        self._mask_wingup = pygame.mask.from_surface(self._img_wingup)
        self._mask_wingdown = pygame.mask.from_surface(self._img_wingdown)

    def update(self, delta_frames=1):
        """Update the bird's position.

        This function uses the cosine function to achieve a smooth climb:
        In the first and last few frames, the bird climbs very little, in the
        middle of the climb, it climbs a lot.
        One complete climb lasts CLIMB_DURATION milliseconds, during which
        the bird ascends with an average speed of CLIMB_SPEED px/ms.
        This Bird's msec_to_climb attribute will automatically be
        decreased accordingly if it was > 0 when this method was called.

        Arguments:
        delta_frames: The number of frames elapsed since this method was
            last called.
        """
        if self.msec_to_climb > 0:
            frac_climb_done = 1 - self.msec_to_climb/Bird.CLIMB_DURATION
            self.y -= (Bird.CLIMB_SPEED * frames_to_msec(delta_frames) *
                       (1 - math.cos(frac_climb_done * math.pi)))
            self.msec_to_climb -= frames_to_msec(delta_frames)
        else:
            self.y += Bird.SINK_SPEED * frames_to_msec(delta_frames)

    @property
    def image(self):
        """Get a Surface containing this bird's image.

        This will decide whether to return an image where the bird's
        visible wing is pointing upward or where it is pointing downward
        based on pygame.time.get_ticks().  This will animate the flapping
        bird, even though pygame doesn't support animated GIFs.
        """
        if pygame.time.get_ticks() % 500 >= 250:
            return self._img_wingup
        else:
            return self._img_wingdown

    @property
    def mask(self):
        """Get a bitmask for use in collision detection.

        The bitmask excludes all pixels in self.image with a
        transparency greater than 127."""
        if pygame.time.get_ticks() % 500 >= 250:
            return self._mask_wingup
        else:
            return self._mask_wingdown

    @property
    def rect(self):
        """Get the bird's position, width, and height, as a pygame.Rect."""
        return Rect(self.x, self.y, Bird.WIDTH, Bird.HEIGHT)


class PipePair(pygame.sprite.Sprite):
    """Represents an obstacle.

    A PipePair has a top and a bottom pipe, and only between them can
    the bird pass -- if it collides with either part, the game is over.

    Attributes:
    x: The PipePair's X position.  This is a float, to make movement
        smoother.  Note that there is no y attribute, as it will only
        ever be 0.
    image: A pygame.Surface which can be blitted to the display surface
        to display the PipePair.
    mask: A bitmask which excludes all pixels in self.image with a
        transparency greater than 127.  This can be used for collision
        detection.
    top_pieces: The number of pieces, including the end piece, in the
        top pipe.
    bottom_pieces: The number of pieces, including the end piece, in
        the bottom pipe.

    Constants:
    WIDTH: The width, in pixels, of a pipe piece.  Because a pipe is
        only one piece wide, this is also the width of a PipePair's
        image.
    PIECE_HEIGHT: The height, in pixels, of a pipe piece.
    ADD_INTERVAL: The interval, in milliseconds, in between adding new
        pipes.
    """

    WIDTH = 80
    PIECE_HEIGHT = 32
    ADD_INTERVAL = 3000

    def __init__(self, pipe_end_img, pipe_body_img):
        """Initialises a new random PipePair.

        The new PipePair will automatically be assigned an x attribute of
        float(WIN_WIDTH - 1).

        Arguments:
        pipe_end_img: The image to use to represent a pipe's end piece.
        pipe_body_img: The image to use to represent one horizontal slice
            of a pipe's body.
        """
        self.x = float(WIN_WIDTH - 1)
        self.y_offset = 0.0
        self.score_counted = False

        self.image = pygame.Surface((PipePair.WIDTH, WIN_HEIGHT), SRCALPHA)
        self.image.convert()   # speeds up blitting
        self.image.fill((0, 0, 0, 0))
        total_pipe_body_pieces = int(
            (WIN_HEIGHT -                  # fill window from top to bottom
             3 * Bird.HEIGHT -             # make room for bird to fit through
             3 * PipePair.PIECE_HEIGHT) /  # 2 end pieces + 1 body piece
            PipePair.PIECE_HEIGHT          # to get number of pipe pieces
        )
        self.bottom_pieces = randint(1, total_pipe_body_pieces)
        self.top_pieces = total_pipe_body_pieces - self.bottom_pieces

        # bottom pipe
        for i in range(1, self.bottom_pieces + 1):
            piece_pos = (0, WIN_HEIGHT - i*PipePair.PIECE_HEIGHT)
            self.image.blit(pipe_body_img, piece_pos)
        bottom_pipe_end_y = WIN_HEIGHT - self.bottom_height_px
        bottom_end_piece_pos = (0, bottom_pipe_end_y - PipePair.PIECE_HEIGHT)
        self.image.blit(pipe_end_img, bottom_end_piece_pos)

        # top pipe
        for i in range(self.top_pieces):
            self.image.blit(pipe_body_img, (0, i * PipePair.PIECE_HEIGHT))
        top_pipe_end_y = self.top_height_px
        self.image.blit(pipe_end_img, (0, top_pipe_end_y))

        # compensate for added end pieces
        self.top_pieces += 1
        self.bottom_pieces += 1

        # for collision detection
        self.mask = pygame.mask.from_surface(self.image)

    @property
    def top_height_px(self):
        """Get the top pipe's height, in pixels."""
        return self.top_pieces * PipePair.PIECE_HEIGHT

    @property
    def bottom_height_px(self):
        """Get the bottom pipe's height, in pixels."""
        return self.bottom_pieces * PipePair.PIECE_HEIGHT

    @property
    def visible(self):
        """Get whether this PipePair on screen, visible to the player."""
        return -PipePair.WIDTH < self.x < WIN_WIDTH

    @property
    def rect(self):
        """Get the Rect which contains this PipePair."""
        return Rect(self.x, self.y_offset, PipePair.WIDTH, WIN_HEIGHT)

    def update(self, delta_frames=1, rising=False):
        """Update the PipePair's position.

        Arguments:
        delta_frames: The number of frames elapsed since this method was
            last called.
        rising: Whether the player is holding space to raise the pipes.
        """
        self.x -= ANIMATION_SPEED * frames_to_msec(delta_frames)
        if rising:
            self.y_offset -= PIPE_RISE_SPEED * frames_to_msec(delta_frames)
        else:
            self.y_offset += PIPE_SINK_SPEED * frames_to_msec(delta_frames)

    def collides_with(self, bird):
        """Get whether the bird collides with a pipe in this PipePair.

        Arguments:
        bird: The Bird which should be tested for collision with this
            PipePair.
        """
        return pygame.sprite.collide_mask(self, bird)


class Spaceship(pygame.sprite.Sprite):
    """A UFO that hunts the bird once 'G' is pressed.

    The player steers it up and down with the arrow keys and fires
    lasers (leftward, toward the bird) with the space bar.

    Constants:
    WIDTH, HEIGHT: The spaceship's dimensions, in pixels.
    MOVE_SPEED: Vertical speed, in pixels per millisecond, while an
        arrow key is held.
    ENTER_SPEED: Speed, in px/ms, at which it flies in from the right.
    """

    WIDTH = 64
    HEIGHT = 30
    MOVE_SPEED = 0.35
    ENTER_SPEED = 0.3

    def __init__(self, y):
        """Create a spaceship just off the right edge of the screen.

        Arguments:
        y: The spaceship's initial (and vertical starting) Y coordinate.
        """
        super(Spaceship, self).__init__()
        self.x = float(WIN_WIDTH)            # start just off-screen right
        self.target_x = float(WIN_WIDTH - Spaceship.WIDTH - 10)
        self.y = float(y)
        self.image = self._build_image()
        self.mask = pygame.mask.from_surface(self.image)

    @staticmethod
    def _build_image():
        """Draw the UFO onto a transparent Surface."""
        surf = pygame.Surface((Spaceship.WIDTH, Spaceship.HEIGHT), SRCALPHA)
        surf.fill((0, 0, 0, 0))
        w, h = Spaceship.WIDTH, Spaceship.HEIGHT
        # saucer body
        pygame.draw.ellipse(surf, (140, 145, 165), (0, h // 2 - 6, w, 18))
        pygame.draw.ellipse(surf, (90, 95, 115), (0, h // 2 + 2, w, 8))
        # glass dome
        pygame.draw.ellipse(surf, (120, 220, 255), (w // 2 - 15, 2, 30, 22))
        # laser barrel pointing left
        pygame.draw.rect(surf, (60, 60, 70), (0, h // 2 - 2, 12, 5))
        return surf

    def update(self, direction, delta_frames=1):
        """Move the spaceship.

        Arguments:
        direction: -1 to move up, +1 to move down, 0 to hold position.
        delta_frames: The number of frames elapsed since the last call.
        """
        if self.x > self.target_x:          # still flying in
            self.x -= Spaceship.ENTER_SPEED * frames_to_msec(delta_frames)
            self.x = max(self.target_x, self.x)
        self.y += direction * Spaceship.MOVE_SPEED * frames_to_msec(delta_frames)
        self.y = max(0, min(WIN_HEIGHT - Spaceship.HEIGHT, self.y))

    @property
    def rect(self):
        """Get the spaceship's position and size, as a pygame.Rect."""
        return Rect(self.x, self.y, Spaceship.WIDTH, Spaceship.HEIGHT)

    @property
    def nose(self):
        """Get the (x, y) point at the front of the laser barrel."""
        return (self.x, self.y + Spaceship.HEIGHT / 2)


class Laser(pygame.sprite.Sprite):
    """A laser bolt fired leftward by the Spaceship.

    Constants:
    WIDTH, HEIGHT: The bolt's dimensions, in pixels.
    SPEED: How fast it travels left, in pixels per millisecond.
    """

    WIDTH = 18
    HEIGHT = 4
    SPEED = 0.8

    def __init__(self, x, y):
        """Create a laser bolt starting at (x, y)."""
        super(Laser, self).__init__()
        self.x = float(x)
        self.y = float(y)

    def update(self, delta_frames=1):
        """Move the laser to the left."""
        self.x -= Laser.SPEED * frames_to_msec(delta_frames)

    @property
    def rect(self):
        """Get the laser's position and size, as a pygame.Rect."""
        return Rect(self.x - Laser.WIDTH, self.y - Laser.HEIGHT / 2,
                    Laser.WIDTH, Laser.HEIGHT)

    @property
    def visible(self):
        """Get whether the laser is still on screen."""
        return self.x > -Laser.WIDTH

    def draw(self, surface):
        """Blit a glowing bolt onto the given surface."""
        pygame.draw.rect(surface, (255, 120, 60), self.rect)
        pygame.draw.rect(surface, (255, 240, 120),
                         (self.x - Laser.WIDTH, self.y - 1, Laser.WIDTH, 2))


def load_images():
    """Load all images required by the game and return a dict of them.

    The returned dict has the following keys:
    background: The game's background image.
    bird-wingup: An image of the bird with its wing pointing upward.
        Use this and bird-wingdown to create a flapping bird.
    bird-wingdown: An image of the bird with its wing pointing downward.
        Use this and bird-wingup to create a flapping bird.
    pipe-end: An image of a pipe's end piece (the slightly wider bit).
        Use this and pipe-body to make pipes.
    pipe-body: An image of a slice of a pipe's body.  Use this and
        pipe-body to make pipes.
    """

    def load_image(img_file_name):
        """Return the loaded pygame image with the specified file name.

        This function looks for images in the game's images folder
        (dirname(__file__)/images/). All images are converted before being
        returned to speed up blitting.

        Arguments:
        img_file_name: The file name (including its extension, e.g.
            '.png') of the required image, without a file path.
        """
        # Look for images relative to this script, so we don't have to "cd" to
        # the script's directory before running it.
        # See also: https://github.com/TimoWilken/flappy-bird-pygame/pull/3
        file_name = os.path.join(os.path.dirname(__file__),
                                 'images', img_file_name)
        img = pygame.image.load(file_name)
        img.convert()
        return img

    return {'background': load_image('background.png'),
            'pipe-end': load_image('pipe_end.png'),
            'pipe-body': load_image('pipe_body.png'),
            # images for animating the flapping bird -- animated GIFs are
            # not supported in pygame
            'bird-wingup': load_image('bird_wing_up.png'),
            'bird-wingdown': load_image('bird_wing_down.png')}


def frames_to_msec(frames, fps=FPS):
    """Convert frames to milliseconds at the specified framerate.

    Arguments:
    frames: How many frames to convert to milliseconds.
    fps: The framerate to use for conversion.  Default: FPS.
    """
    return 1000.0 * frames / fps


def msec_to_frames(milliseconds, fps=FPS):
    """Convert milliseconds to frames at the specified framerate.

    Arguments:
    milliseconds: How many milliseconds to convert to frames.
    fps: The framerate to use for conversion.  Default: FPS.
    """
    return fps * milliseconds / 1000.0


def main():
    """The application's entry point.

    If someone executes this module (instead of importing it, for
    example), this function is called.
    """

    pygame.init()

    display_surface = pygame.display.set_mode((WIN_WIDTH, WIN_HEIGHT))
    pygame.display.set_caption('Pygame Flappy Bird')

    clock = pygame.time.Clock()
    score_font = pygame.font.SysFont(None, 32, bold=True)  # default font
    countdown_font = pygame.font.SysFont(None, 140, bold=True)
    images = load_images()

    bird = Bird(int(WIN_WIDTH/2 - Bird.WIDTH/2), int(WIN_HEIGHT/2 - Bird.HEIGHT/2), 0,
                (images['bird-wingup'], images['bird-wingdown']))

    pipes = deque()

    # Hunt-mode state: activated by pressing 'G'.  A spaceship flies in,
    # pipes stop spawning, and the goal flips to shooting down the bird.
    hunt_mode = False
    spaceship = None
    lasers = deque()
    bird_alive = True
    # Frames left in the "3, 2, 1, GO!" intro before the player takes
    # control of the spaceship.  0 means controls are live.
    countdown_left = 0

    frame_clock = 0  # this counter is only incremented if the game isn't paused
    score = 0
    done = paused = False
    while not done:
        clock.tick(FPS)

        # Handle this 'manually'.  If we used pygame.time.set_timer(),
        # pipe addition would be messed up when paused.
        if not (paused or hunt_mode or
                frame_clock % msec_to_frames(PipePair.ADD_INTERVAL)):
            pp = PipePair(images['pipe-end'], images['pipe-body'])
            pipes.append(pp)

        for e in pygame.event.get():
            if e.type == QUIT or (e.type == KEYUP and e.key == K_ESCAPE):
                done = True
                break
            elif e.type == KEYUP and e.key in (K_PAUSE, K_p):
                paused = not paused
            elif e.type == KEYDOWN and e.key == K_g and not hunt_mode:
                # Summon the spaceship; a short countdown gives the player
                # a moment before the hunt begins.
                hunt_mode = True
                countdown_left = int(4 * FPS)   # "3", "2", "1", "GO!"
                spaceship = Spaceship(bird.y + Bird.HEIGHT / 2 -
                                      Spaceship.HEIGHT / 2)
            elif (e.type == KEYDOWN and e.key == K_SPACE
                    and hunt_mode and bird_alive and countdown_left <= 0):
                # Fire a laser from the spaceship's barrel.
                nose_x, nose_y = spaceship.nose
                lasers.append(Laser(nose_x, nose_y))

        if paused:
            continue  # don't draw anything

        keys = pygame.key.get_pressed()
        # In hunt mode the space bar fires lasers, so it no longer raises
        # the pipes.
        rising = keys[K_SPACE] and not hunt_mode

        # check for collisions -- pipes only threaten the bird before the
        # hunt begins; afterwards the bird is the target, not the player.
        if not hunt_mode:
            pipe_collision = any(p.collides_with(bird) for p in pipes)
            if pipe_collision:
                done = True

        for x in (0, WIN_WIDTH / 2):
            display_surface.blit(images['background'], (x, 0))

        while pipes and not pipes[0].visible:
            pipes.popleft()

        for p in pipes:
            p.update(rising=rising)
            display_surface.blit(p.image, p.rect)

        # Hunt mode: move the spaceship, advance lasers, check for a hit.
        if hunt_mode:
            # During the countdown the ship flies in but the player
            # can't steer or fire yet.
            controls_live = countdown_left <= 0
            direction = (keys[K_DOWN] - keys[K_UP]) if controls_live else 0
            spaceship.update(direction)

            if controls_live:
                while lasers and not lasers[0].visible:
                    lasers.popleft()
                for laser in lasers:
                    laser.update()
                    laser.draw(display_surface)
                    if bird_alive and laser.rect.colliderect(bird.rect):
                        bird_alive = False

            display_surface.blit(spaceship.image, spaceship.rect)

            # Draw the "3, 2, 1, GO!" overlay and count it down.
            if countdown_left > 0:
                seconds_left = math.ceil(countdown_left / FPS)
                text = 'GO!' if seconds_left <= 1 else str(seconds_left - 1)
                cd_surface = countdown_font.render(text, True, (255, 240, 120))
                display_surface.blit(
                    cd_surface,
                    (WIN_WIDTH / 2 - cd_surface.get_width() / 2,
                     WIN_HEIGHT / 2 - cd_surface.get_height() / 2))
                countdown_left -= 1

        if bird_alive:
            display_surface.blit(bird.image, bird.rect)
        elif hunt_mode:
            # The bird is down -- announce it and end the game shortly after.
            msg = score_font.render('BIRD DOWN!', True, (255, 80, 80))
            display_surface.blit(
                msg, (WIN_WIDTH / 2 - msg.get_width() / 2,
                      WIN_HEIGHT / 2 - msg.get_height() / 2))
            pygame.display.flip()
            pygame.time.wait(1500)
            done = True

        # update and display score
        for p in pipes:
            if p.x + PipePair.WIDTH < bird.x and not p.score_counted:
                score += 1
                p.score_counted = True

        score_surface = score_font.render(str(score), True, (255, 255, 255))
        score_x = WIN_WIDTH/2 - score_surface.get_width()/2
        display_surface.blit(score_surface, (score_x, PipePair.PIECE_HEIGHT))

        pygame.display.flip()
        frame_clock += 1
    print('Game over! Score: %i' % score)
    pygame.quit()


if __name__ == '__main__':
    # If this module had been imported, __name__ would be 'flappybird'.
    # It was executed (e.g. by double-clicking the file), so call main.
    main()
