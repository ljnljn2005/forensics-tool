"""Selects fittest individuals from given population."""

import random
import bisect


def roulette_selection(population, elites=4):
    """Roulette wheel selection.

    Each individual is selected to reproduce, with probability directly
    proportional to its fitness score.

    :params population: Collection of the individuals for selecting.
    :params elite: Number of elite individuals passed to next generation.

    Usage::

        >>> from gaps.selection import roulette_selection
        >>> selected_parents = roulette_selection(population, 10)

    """
    fitness_values = [individual.fitness for individual in population]
    probability_intervals = [
        sum(fitness_values[: i + 1]) for i in range(len(fitness_values))
    ]

    def select_individual():
        """Selects random individual from population based on fitess value"""
        random_select = random.uniform(0, probability_intervals[-1])
        selected_index = bisect.bisect_left(probability_intervals, random_select)
        return population[selected_index]

    selected = []
    for i in range(len(population) - elites):
        first, second = select_individual(), select_individual()
        selected.append((first, second))

    return selected


def tournament_selection(population, elites=4, tournament_size=3):
    """Tournament selection - better diversity preservation than roulette.

    Randomly picks 'tournament_size' individuals and selects the fittest.
    This prevents single high-fitness individuals from dominating reproduction.

    :params population: Collection of the individuals for selecting.
    :params elites: Number of elite individuals passed to next generation.
    :params tournament_size: Number of individuals competing in each tournament.
    """
    selected = []
    num_parents = len(population) - elites

    for _ in range(num_parents):
        tournament = random.sample(population, min(tournament_size, len(population)))
        first = max(tournament, key=lambda ind: ind.fitness)

        tournament = random.sample(population, min(tournament_size, len(population)))
        second = max(tournament, key=lambda ind: ind.fitness)

        selected.append((first, second))

    return selected


def rank_selection(population, elites=4):
    """Rank-based selection - reduces selection pressure and prevents
    premature convergence by using ranks instead of raw fitness values."""
    sorted_pop = sorted(population, key=lambda ind: ind.fitness)
    n = len(sorted_pop)
    ranks = list(range(1, n + 1))
    total_rank = sum(ranks)
    probability_intervals = [
        sum(ranks[: i + 1]) for i in range(n)
    ]

    def select_individual():
        random_select = random.uniform(0, total_rank)
        selected_index = bisect.bisect_left(probability_intervals, random_select)
        return sorted_pop[selected_index]

    selected = []
    for _ in range(n - elites):
        first, second = select_individual(), select_individual()
        selected.append((first, second))

    return selected
