from __future__ import print_function

from operator import attrgetter

import numpy as np

from gaps import utils
from gaps.crossover import Crossover
from gaps.fitness import local_search_improve
from gaps.image_analysis import ImageAnalysis
from gaps.individual import Individual
from gaps.plot import Plot
from gaps.progress_bar import print_progress
from gaps.selection import roulette_selection, tournament_selection, rank_selection


class GeneticAlgorithm(object):
    TERMINATION_THRESHOLD = 10

    def __init__(self, image, piece_size, population_size, generations,
                 elite_size=2, selection_method="tournament", mutation_rate=0.02):
        self._image = image
        self._piece_size = piece_size
        self._generations = generations
        self._elite_size = elite_size
        self._selection_method = selection_method
        self._mutation_rate = mutation_rate
        pieces, rows, columns = utils.flatten_image(image, piece_size, indexed=True)
        self._population = [
            Individual(pieces, rows, columns) for _ in range(population_size)
        ]
        self._pieces = pieces

    def _compute_population_diversity(self):
        """Measure population diversity by counting unique fitness values."""
        fitnesses = [ind.fitness for ind in self._population]
        unique_ratio = len(set(round(f, 4) for f in fitnesses)) / len(fitnesses)
        return unique_ratio

    def start_evolution(self, verbose):
        print("=== Pieces:      {}".format(len(self._pieces)))
        print("=== Selection:   {}".format(self._selection_method))
        print("=== Mutation:    {}\n".format(self._mutation_rate))

        if verbose:
            plot = Plot(self._image)

        ImageAnalysis.analyze_image(self._pieces)

        # Adaptive termination: scale threshold with piece count
        total_pieces = len(self._pieces)
        adaptive_threshold = max(10, min(50, total_pieces // 4))
        print("=== Termination threshold: {}\n".format(adaptive_threshold))

        fittest = None
        best_fitness_score = float("-inf")
        termination_counter = 0
        stagnation_restart_counter = 0

        for generation in range(self._generations):
            print_progress(
                generation, self._generations - 1, prefix="=== Solving puzzle: "
            )

            new_population = []

            # Elitism
            elite = self._get_elite_individuals(elites=self._elite_size)
            new_population.extend(elite)

            # Selection
            if self._selection_method == "roulette":
                selected_parents = roulette_selection(
                    self._population, elites=self._elite_size
                )
            elif self._selection_method == "rank":
                selected_parents = rank_selection(
                    self._population, elites=self._elite_size
                )
            else:
                selected_parents = tournament_selection(
                    self._population, elites=self._elite_size
                )

            for first_parent, second_parent in selected_parents:
                crossover = Crossover(first_parent, second_parent)
                crossover.run()
                child = crossover.child()
                # Apply mutation
                child.mutate(self._mutation_rate)
                new_population.append(child)

            # Diversity check and restart if needed
            self._population = new_population
            diversity = self._compute_population_diversity()
            if diversity < 0.15 and stagnation_restart_counter < 3:
                stagnation_restart_counter += 1
                print("\n=== Low diversity ({:.2f}), injecting random individuals".format(diversity))
                pieces, rows, columns = utils.flatten_image(
                    self._image, self._piece_size, indexed=True
                )
                n_random = max(2, len(self._population) // 5)
                for i in range(n_random):
                    new_ind = Individual(pieces, rows, columns, shuffle=True)
                    self._population[i] = new_ind

            fittest = self._best_individual()

            if fittest.fitness <= best_fitness_score:
                termination_counter += 1
            else:
                best_fitness_score = fittest.fitness
                termination_counter = 0

            if termination_counter >= adaptive_threshold:
                print("\n\n=== GA terminated")
                print(
                    "=== No improvement for {} generations".format(
                        termination_counter
                    )
                )
                print("\n=== Running local search refinement...")
                fittest = local_search_improve(fittest)
                print("=== Local search complete")
                return fittest

            if verbose:
                plot.show_fittest(
                    fittest.to_image(),
                    "Generation: {} / {}".format(generation + 1, self._generations),
                )

        # Post-GA local search hill climbing
        print("\n=== Running local search refinement...")
        fittest = local_search_improve(fittest)
        print("=== Local search complete")

        return fittest

    def _get_elite_individuals(self, elites):
        """Returns first 'elite_count' fittest individuals from population"""
        return sorted(self._population, key=attrgetter("fitness"))[-elites:]

    def _best_individual(self):
        """Returns the fittest individual from population"""
        return max(self._population, key=attrgetter("fitness"))
