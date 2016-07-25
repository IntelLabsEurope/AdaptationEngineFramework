"""
Copyright 2016 INTEL RESEARCH AND INNOVATION IRELAND LIMITED

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""
import logging

import adaptationengine_framework.adaptationaction as adaptationaction

LOGGER = logging.getLogger('syslog')


class Voter:
    """
    an object to keep track of plugins ('voters') and who they voted for

    we're assuming a voter will be unique to a plugin round
    """

    def __init__(self, name):
        self.name = name
        self.votes = []

    def vote(self, preference, candidate_id):
        """
        fill candidate_id into appropriate place in votes list,
        or expand votes list until the place is created
        """
        try:
            self.votes[preference] = candidate_id
        except IndexError:
            self.votes.append(0)
            self.vote(preference, candidate_id)


class Candidate(adaptationaction.AdaptationAction):
    """a wrapper for adaptation actions to add some additional info"""

    def __init__(self, action):
        self.action = action
        self.supporters = {}
        self.votes = [0]
        self.id = hash(action)

    def __getattr__(self, key):
        """
        pass through attribute requests to the AdaptationAction object unless
        it's candidate-specific
        """
        if (
                key is 'votes' or
                key is 'id' or
                key is 'supporters'
        ):
            return getattr(self, key)
        else:
            return getattr(self.action, key)

    def __repr__(self):
        output = (
            "Candidate(id={id}, "
            "type={type}, "
            "target={target}, "
            "destination={destination},"
            " scale_value={scale_value},"
            " votes={votes})").format(
                id=self.id,
                type=(
                    adaptationaction.AdaptationType.get_string(
                        self.adaptation_type
                    )
                ),
                target=self.target,
                destination=self.destination,
                scale_value=self.scale_value,
                votes=self.votes
        )
        return output

    def add_votes(self, supporter, amount, seat=1):
        """
        fill votes into appropriate place in votes list,
        or expand votes list until the place is created. also add an
        entry into the supporters list
        """
        try:
            self.votes[seat] += amount
            self.supporters.setdefault(seat, [])
            self.supporters[seat] += [supporter]
        except IndexError:
            self.votes.append(0)
            self.add_votes(supporter, amount, seat)

    def add_transfer(self, amount, seat):
        """
        fill votes into appropriate place in votes list,
        or expand votes list until the place is created
        """
        try:
            self.votes[seat] += amount
        except IndexError:
            self.votes.append(0)
            self.add_transfer(amount, seat)


class SingleTransferrableVote:
    """
    take a plugin-round-results dictionary and use the STV method to re-order
    and combine the lists of adaptation actions
    """

    @staticmethod
    def _transfer_votes(
            win_or_lose, transferer, hopefuls, voters, seat, quota
    ):
        """
        transfer votes from either a vinning candidate or an excluded one,
        in ratio of the preferences of voters who voted for the candidate
        """
        surplus_votes = transferer.votes[seat] - quota

        if win_or_lose:
            # winner
            total_transferrable_votes = surplus_votes
        else:
            total_transferrable_votes = sum(transferer.votes)

        # get next highest valid preference of whoever voted for this guy
        receipients = {}

        for voter in voters:
            # did you vote for this guy
            if transferer.id in voter.votes:
                # if so, who is your next choice that hasn't
                # been elected or removed
                p = voter.votes.index(transferer.id) + 1
                while True:
                    try:
                        next_preference = (voter.votes[p])
                        if next_preference in [h.id for h in hopefuls]:
                            receipients.setdefault(next_preference, 0)
                            receipients[next_preference] += 1
                            break
                        else:
                            p += 1
                    except IndexError:
                        break

        if receipients:
            # if there is some, split transferer's votes between them
            total_preferences = sum(receipients.itervalues())

            for candidate in hopefuls:
                if candidate.id in receipients.iterkeys():
                    ratio = (
                        float(receipients[candidate.id]) / total_preferences
                    )
                    votes_transferred = int(total_transferrable_votes * ratio)
                    if win_or_lose:
                        candidate.add_transfer(votes_transferred, seat + 1)
                    else:
                        candidate.add_transfer(votes_transferred, seat)
        else:
            # if not, split transferer's vote between all hopefuls
            total_candidates = len(hopefuls)
            votes_transferred = int(
                total_transferrable_votes / total_candidates
            )

            for candidate in hopefuls:
                if win_or_lose:
                    candidate.add_transfer(votes_transferred, seat + 1)
                else:
                    candidate.add_transfer(votes_transferred, seat)

        return hopefuls

    @staticmethod
    def tally(round_results, blacklist):
        """tally up the votes"""
        hopefuls = []
        all_voters = []
        winners = []
        excluded = []
        final_list = []
        seats_to_fill = 0
        total_number_of_votes = 0

        total_plugin_weight = sum(
            [plugin['weight'] for key, plugin in round_results.items()]
        )

        # find any action with a score of -1 and add to blacklist
        for plugin_name, plugin_data in round_results.items():
            for action in plugin_data.get('results', []):
                if action.score == -1:
                    LOGGER.info("Adding to blacklist {}".format(action))
                    blacklist.append(action)

        # and remove it from all lists
        for plugin_name, plugin_data in round_results.items():
            results_copy = list(plugin_data.get('results', []))
            for action in results_copy:
                if action in blacklist:
                    LOGGER.info(
                        "Removing blacklisted action {}".format(action)
                    )
                    round_results[plugin_name]['results'].remove(action)

        LOGGER.info("Valid Round results: {}". format(round_results))
        # now actually go through results
        for plugin_name, plugin_results in round_results.items():
            voter = Voter(plugin_name)
            all_voters.append(voter)

            # remove duplicate actions from plugin
            results = list(set(plugin_results['results']))

            # normalise plugin weight
            weight = float(plugin_results['weight']) / total_plugin_weight

            for preference, action in enumerate(results):
                votes = int((action.score * 1000) * weight)
                candidate = Candidate(action)

                if candidate not in hopefuls:
                    hopefuls.append(candidate)
                else:
                    candidate = hopefuls[hopefuls.index(candidate)]

                candidate.add_votes(plugin_name, votes, preference)
                voter.vote(preference, candidate.id)
                total_number_of_votes += votes

        # extend candidates' vote lists to the same length
        seats_to_fill = len(hopefuls)
        for candidate in hopefuls:
            num_preferences = len(candidate.votes)

            if num_preferences < seats_to_fill:
                candidate.votes += ([0] * (seats_to_fill - num_preferences))

        # calculate quota (droop) (total votes / seats + 1) + 1
        quota = (total_number_of_votes / (seats_to_fill + 1)) + 1

        # tally
        LOGGER.info("Voting quota: {}".format(quota))
        for seat in xrange(seats_to_fill):
            winner = False
            while not winner and len(hopefuls) > 1:
                LOGGER.info("Tallying for seat {}".format(seat + 1))

                # sort by score
                hopefuls.sort(
                    key=lambda candidate: candidate.votes[seat], reverse=True
                )

                # everyone with more X PREFERENCE votes than quota gets in
                removed_candidate = None
                for candidate in hopefuls:
                    if candidate.votes[seat] >= quota:
                        # add winner to final list
                        winners.append(candidate)
                        hopefuls.remove(candidate)
                        removed_candidate = candidate
                        winner = True
                        break  # we found a winner, exit loop

                if winner:
                    hopefuls = SingleTransferrableVote._transfer_votes(
                        True,
                        removed_candidate,
                        hopefuls,
                        all_voters,
                        seat,
                        quota
                    )
                    LOGGER.info(
                        "Candidate {} won the seat".format(removed_candidate)
                    )
                else:
                    # if nobody reaches the quota, remove the lowest and
                    # transfer their votes to the top
                    candidate = hopefuls[-1]
                    hopefuls.remove(candidate)
                    excluded.append(candidate)
                    hopefuls = SingleTransferrableVote._transfer_votes(
                        False,
                        candidate,
                        hopefuls,
                        all_voters,
                        seat,
                        quota=0
                    )

                    LOGGER.debug("Excluded candidate {}".format(candidate))

        # put the vote value in place of score for the final output
        for i, val in enumerate(winners):
            winners[i].action.votes = val.votes[0]
        for i, val in enumerate(hopefuls):
            hopefuls[i].action.votes = val.votes[0]
        for i, val in enumerate(excluded):
            excluded[i].action.votes = val.votes[0]

		# add winners
        final_list = [winner.action for winner in winners]
        # add remaining hopefuls
        final_list += [hopeful.action for hopeful in hopefuls]
        # add losers
        excluded.reverse()
        final_list += [loser.action for loser in excluded]

        # return results and new blacklist
        return (final_list, blacklist)
