import numpy as np

from gaps import utils
from gaps.image_analysis import ImageAnalysis


class Individual(object):
    """Class representing possible solution to puzzle.

    Individual object is one of the solutions to the problem
    (possible arrangement of the puzzle's pieces).
    It is created by random shuffling initial puzzle.

    :param pieces:  Array of pieces representing initial puzzle.
    :param rows:    Number of rows in input puzzle
    :param columns: Number of columns in input puzzle

    Usage::

        >>> from gaps.individual import Individual
        >>> from gaps.image_helpers import flatten_image
        >>> pieces, rows, columns = flatten_image(...)
        >>> ind = Individual(pieces, rows, columns)

    """

    FITNESS_FACTOR = 1000

    def __init__(self, pieces, rows, columns, shuffle=True):
        self.pieces = pieces[:]
        self.rows = rows
        self.columns = columns
        self._fitness = None

        if shuffle:
            np.random.shuffle(self.pieces)

        self._piece_mapping = {
            piece.id: index for index, piece in enumerate(self.pieces)
        }

    def __getitem__(self, key):
        return self.pieces[key * self.columns : (key + 1) * self.columns]

    @property
    def fitness(self):
        """Evaluates fitness value.

        Fitness value is calculated as sum of dissimilarity measures between
        each adjacent pieces.

        """
        if self._fitness is None:
            fitness_value = 1.0 / self.FITNESS_FACTOR
            for i in range(self.rows):
                for j in range(self.columns - 1):
                    ids = (self[i][j].id, self[i][j + 1].id)
                    fitness_value += ImageAnalysis.get_dissimilarity(
                        ids, orientation="LR"
                    )
            for i in range(self.rows - 1):
                for j in range(self.columns):
                    ids = (self[i][j].id, self[i + 1][j].id)
                    fitness_value += ImageAnalysis.get_dissimilarity(
                        ids, orientation="TD"
                    )

            self._fitness = self.FITNESS_FACTOR / fitness_value

        return self._fitness

    def piece_size(self):
        """Returns single piece size"""
        return self.pieces[0].size

    def piece_by_id(self, identifier):
        """ "Return specific piece from individual"""
        return self.pieces[self._piece_mapping[identifier]]

    def to_image(self):
        """Converts individual to showable image"""
        pieces = [piece.image for piece in self.pieces]
        return utils.assemble_image(pieces, self.rows, self.columns)

    def edge(self, piece_id, orientation):
        edge_index = self._piece_mapping[piece_id]

        if (orientation == "T") and (edge_index >= self.columns):
            return self.pieces[edge_index - self.columns].id

        if (orientation == "R") and (edge_index % self.columns < self.columns - 1):
            return self.pieces[edge_index + 1].id

        if (orientation == "D") and (edge_index < (self.rows - 1) * self.columns):
            return self.pieces[edge_index + self.columns].id

        if (orientation == "L") and (edge_index % self.columns > 0):
            return self.pieces[edge_index - 1].id

    def mutate(self, mutation_rate=0.02):
        """Swap pairs of pieces randomly to introduce diversity.

        :param mutation_rate: Probability of swapping each piece.
        """
        if np.random.random() > 0.3:
            return
        n_swaps = max(1, int(len(self.pieces) * mutation_rate))
        for _ in range(n_swaps):
            i, j = np.random.choice(len(self.pieces), 2, replace=False)
            self.pieces[i], self.pieces[j] = self.pieces[j], self.pieces[i]
            self._piece_mapping[self.pieces[i].id] = i
            self._piece_mapping[self.pieces[j].id] = j
        self._fitness = None

    def copy(self):
        """Creates a deep copy of this individual without fitness cache."""
        other = Individual(self.pieces, self.rows, self.columns, shuffle=False)
        return other
