import numpy as np
import torch
import torch.nn.functional as F
from torch.autograd import Variable
from torch.distributions import Categorical

from torchrl.models import PGModel
from torchrl.utils import nn_from_config, discounted_sum_rewards


class ReinforceModel(PGModel):
    '''
    REINFORCE model.
    '''

    def __init__(self, policy_nn_config, value_nn_config=None, share_body=False,
                 **kwargs):
        self.policy_nn_config = policy_nn_config
        self.value_nn_config = value_nn_config
        self.share_body = share_body
        self.saved_log_probs = []
        self.saved_state_values = []

        super().__init__(
            policy_nn_config=policy_nn_config, value_nn_config=value_nn_config, **kwargs)

    def add_pg_loss(self, batch):
        '''
        Compute loss based on the policy gradient theorem.

        Parameters
        ----------
        batch: dict
            The batch should contain all the information necessary
            to compute the gradients.
        '''
        returns = self._to_variable(discounted_sum_rewards(batch['rewards']))

        if self.value_nn is not None:
            state_values = torch.cat(self.saved_state_values).view(-1)
            returns = returns - state_values

        log_probs = torch.cat(self.saved_log_probs).view(-1)
        objective = log_probs * returns
        loss = -objective.sum()

        self.losses.append(loss)

    def add_value_nn_loss(self, batch):
        returns = self._to_variable(discounted_sum_rewards(batch['rewards']))
        state_values = torch.cat(self.saved_state_values).view(-1)

        loss = F.mse_loss(input=state_values, target=returns)

        self.losses.append(loss)

    def add_losses(self, batch):
        '''
        Define all losses used for calculating the gradient.

        Parameters
        ----------
        batch: dict
            The batch should contain all the information necessary
            to compute the gradients.
        '''
        self.add_pg_loss(batch)
        self.add_value_nn_loss(batch)

        self.saved_log_probs = []
        self.saved_state_values = []
