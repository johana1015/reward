import pdb
import torch
import torchrl.utils as U
from torchrl.agents import BaseAgent


class DDPGAgent(BaseAgent):
    def __init__(
        self,
        actor,
        critic,
        batcher,
        optimizer,
        action_fn,
        q_target=U.estimators.value.TDTarget(gamma=0.99),
        log_dir=None,
        **kwargs
    ):
        super().__init__(
            batcher=batcher,
            optimizer=optimizer,
            action_fn=action_fn,
            log_dir=log_dir,
            **kwargs
        )
        self.register_model("actor", actor)
        self.register_model("critic", critic)

        self.q_target = q_target

    def step(self):
        batch = self.generate_batch()
        self.add_q_target(batch)

        batch = batch.concat_batch()
        self.train_models(batch)

    def add_q_target(self, batch):
        with torch.no_grad():
            state_tp1 = U.join_first_dims(batch.state_tp1, num_dims=2)
            act_target = self.models.actor.forward_target(state_tp1)
            q_tp1 = self.models.critic.forward_target((state_tp1, act_target))
            q_tp1 = q_tp1.reshape(batch.reward.shape)

            batch.state_value_tp1 = q_tp1
            batch.q_target = self.q_target(batch)
            assert batch.q_target.shape == batch.reward.shape
