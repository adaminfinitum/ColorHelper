"""Gamut handling."""
from ... import util
from ... spaces import Angle, Cylindrical, GamutBound
from abc import ABCMeta, abstractmethod


def clip_channels(color):
    """Clip channels."""

    channels = util.no_nan(color.coords())
    gamut = color._space.RANGE
    fit = []

    for i, value in enumerate(channels):
        a, b = gamut[i]
        is_bound = isinstance(gamut[i], GamutBound)

        # Wrap the angle. Not technically out of gamut, but we will clean it up.
        if isinstance(a, Angle) and isinstance(b, Angle):
            fit.append(value % 360.0)
            continue

        # These parameters are unbounded
        if not is_bound:  # pragma: no cover
            # Will not execute unless we have a space that defines some coordinates
            # as bound and others as not. We do not currently have such spaces.
            a = None
            b = None

        # Fit value in bounds.
        fit.append(util.clamp(value, a, b))
    return fit


class Fit(ABCMeta):
    """Fit plugin class."""

    @staticmethod
    @abstractmethod
    def name():
        """Get name of method."""

    @staticmethod
    @abstractmethod
    def distance(color):
        """Get coordinates of the new gamut mapped color."""


class Gamut:
    """Handle gamut related functions."""

    def clip(self, space=None, *, in_place=False):
        """Clip the color channels."""

        if space is None:
            space = self.space()

        this = self.clone() if not in_place else self

        # Convert to desired space
        c = self.convert(space)

        # If we are perfectly in gamut, don't waste time clipping.
        if c.in_gamut(tolerance=0.0):
            if isinstance(c._space, Cylindrical):
                name = c._space.hue_name()
                c.set(name, util.constrain_hue(c.get(name)))
        else:
            c._space._coords = clip_channels(c)
        c.normalize()

        # Adjust "this" color
        return this.update(c)

    def fit(self, space=None, *, method=None, in_place=False):
        """Fit the gamut using the provided method."""

        # Dedicated clip method.
        if method == 'clip' or (method is None and self.FIT == "clip"):
            return self.clip(space, in_place=in_place)

        if space is None:
            space = self.space()

        if method is None:
            method = self.FIT

        this = self.clone() if not in_place else self

        # Select appropriate mapping algorithm
        if method in self.FIT_MAP:
            func = self.FIT_MAP[method]
        else:
            # Unknown fit method
            raise ValueError("'{}' gamut mapping is not currently supported".format(method))

        # Convert to desired space
        c = self.convert(space)

        # If we are perfectly in gamut, don't waste time fitting, just normalize hues.
        # If out of gamut, apply mapping/clipping/etc.
        if c.in_gamut(tolerance=0.0):
            if isinstance(c._space, Cylindrical):
                name = c._space.hue_name()
                c.set(name, util.constrain_hue(c.get(name)))
        else:
            c._space._coords = func(c)
        c.normalize()

        # Adjust "this" color
        return this.update(c)

    def in_gamut(self, space=None, *, tolerance=util.DEF_FIT_TOLERANCE):
        """Check if current color is in gamut."""

        space = space.lower() if space is not None else self.space()

        # Check gamut in the provided space
        if space is not None and space != self.space():
            c = self.convert(space)
            return c.in_gamut(tolerance=tolerance)

        # Check the color space specified for gamut checking.
        # If it proves to be in gamut, we will then test if the current
        # space is constrained properly.
        if self._space.GAMUT_CHECK is not None:
            c = self.convert(self._space.GAMUT_CHECK)
            if not c.in_gamut(tolerance=tolerance):
                return False

        # Verify the values are in bound
        channels = util.no_nan(self.coords())
        for i, value in enumerate(channels):
            a, b = self._space.RANGE[i]
            is_bound = isinstance(self._space.RANGE[i], GamutBound)

            # Angles will wrap, so no sense checking them
            if isinstance(a, Angle):
                continue

            # These parameters are unbounded
            if not is_bound:
                a = None
                b = None

            # Check if bounded values are in bounds
            if (a is not None and value < (a - tolerance)) or (b is not None and value > (b + tolerance)):
                return False

        return True
