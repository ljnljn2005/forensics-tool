import numpy as np


def dissimilarity_measure(first_piece, second_piece, orientation="LR"):
    """Calculates color difference over all neighboring pixels over all color channels.

    The dissimilarity measure relies on the premise that adjacent jigsaw pieces
    in the original image tend to share similar colors along their abutting
    edges, i.e., the sum (over all neighboring pixels) of squared color
    differences (over all three color bands) should be minimal.

    :params first_piece:  First input piece for calculation.
    :params second_piece: Second input piece for calculation.
    :params orientation:  How input pieces are oriented.

                          LR => 'Left - Right'
                          TD => 'Top - Down'

    Usage::

        >>> from gaps.fitness import dissimilarity_measure
        >>> from gaps.piece import Piece
        >>> p1, p2 = Piece(), Piece()
        >>> dissimilarity_measure(p1, p2, orientation="TD")

    """
    rows, columns, _ = first_piece.shape()
    color_difference = None

    # | L | - | R |
    if orientation == "LR":
        color_difference = (
            first_piece[:rows, columns - 1, :] - second_piece[:rows, 0, :]
        )

    # | T |
    #   |
    # | D |
    if orientation == "TD":
        color_difference = (
            first_piece[rows - 1, :columns, :] - second_piece[0, :columns, :]
        )

    squared_color_difference = np.power(color_difference / 255.0, 2)
    color_difference_per_row = np.sum(squared_color_difference, axis=1)
    total_difference = np.sum(color_difference_per_row, axis=0)

    value = np.sqrt(total_difference)

    return value


def local_search_improve(individual, max_iterations=2000):
    """Hill-climbing local search: try swapping pairs and keep if fitness improves.

    This addresses the GA's inability to fine-tune solutions near the optimum.
    Uses a focused window approach for efficiency on large puzzles.
    """
    best_fitness = individual.fitness
    iteration = 0
    n_pieces = len(individual.pieces)
    max_swaps = min(max_iterations, n_pieces * 4)
    no_improve_count = 0

    while iteration < max_swaps and no_improve_count < 500:
        i, j = np.random.choice(n_pieces, 2, replace=False)

        individual.pieces[i], individual.pieces[j] = (
            individual.pieces[j],
            individual.pieces[i],
        )
        individual._piece_mapping[individual.pieces[i].id] = i
        individual._piece_mapping[individual.pieces[j].id] = j
        individual._fitness = None

        new_fitness = individual.fitness

        if new_fitness > best_fitness:
            best_fitness = new_fitness
            no_improve_count = 0
        else:
            individual.pieces[i], individual.pieces[j] = (
                individual.pieces[j],
                individual.pieces[i],
            )
            individual._piece_mapping[individual.pieces[i].id] = i
            individual._piece_mapping[individual.pieces[j].id] = j
            individual._fitness = None
            no_improve_count += 1

        iteration += 1

    return individual
