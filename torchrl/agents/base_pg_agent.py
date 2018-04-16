import numpy as np
import torchrl.utils as U
from torchrl.agents import BatchAgent
from torchrl.models import BasePGModel, ValueModel


class BasePGAgent(BatchAgent):
    def __init__(self,
                 env,
                 policy_model_class,
                 policy_nn,
                 value_nn=None,
                 advantage=U.estimators.advantage.GAE(gamma=0.99, gae_lambda=0.95),
                 vtarget=U.estimators.value.GAE(),
                 **kwargs):
        self.policy_model_class = policy_model_class
        self.policy_nn = policy_nn
        self.value_nn = value_nn
        self.advantage = advantage
        self.vtarget = vtarget

        super().__init__(env, **kwargs)

    def create_models(self):
        assert issubclass(self.policy_model_class, BasePGModel), \
            'Policy Model class must be subclass of BasePGModel'
        # TODO: Some models might need additional parameters
        self.policy_model = self.policy_model_class(
            model=self.policy_nn, action_info=self.env.action_info, logger=self.logger)

        if self.value_nn is not None:
            self.value_model = ValueModel(self.value_nn, logger=self.logger)
        else:
            self.value_model = None

    def step(self):
        batch = self.generate_batch(self.steps_per_batch, self.episodes_per_batch)

        self.add_state_value(batch)
        self.add_advantage(batch)
        self.add_vtarget(batch)

        self.policy_model.train(batch)
        self.value_model.train(batch)

    def add_state_value(self, batch):
        if self.value_model is not None:
            batch.state_value = U.to_numpy(self.value_model(batch.state_t).view(-1))

    def add_advantage(self, batch):
        batch.advantage = self.advantage(batch)

    def add_vtarget(self, batch):
        batch.vtarget = self.vtarget(batch)

    @classmethod
    def from_config(cls, config, env=None, policy_model_class=None, **kwargs):
        if env is None:
            env = U.env_from_config(config)

        # If the policy_model_class is given it should overwrite key from config
        if policy_model_class is not None:
            config.pop('policy_model_class')
        else:
            policy_model_class = config.pop('policy_model_class')

        policy_nn_config = config.pop('policy_nn_config')
        value_nn_config = config.pop('value_nn_config', None)

        policy_nn = U.nn_from_config(policy_nn_config, env.state_info, env.action_info)
        if value_nn_config is not None:
            if value_nn_config.get('body') is None:
                print('Policy NN and Value NN are sharing bodies')
                value_nn_body = policy_nn.layers[0]
            else:
                print('Policy NN and Value NN are using different bodies')
                value_nn_body = None
            value_nn = U.nn_from_config(
                value_nn_config, env.state_info, env.action_info, body=value_nn_body)
        else:
            value_nn = None

        return cls(
            env=env,
            policy_model_class=policy_model_class,
            policy_nn=policy_nn,
            value_nn=value_nn,
            **config.as_dict(),
            **kwargs)
