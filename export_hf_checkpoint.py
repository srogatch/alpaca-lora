import os

import torch
import transformers
from peft import PeftModel
from transformers import LlamaForCausalLM, LlamaTokenizer  # noqa: F402
import argparse

args_parser = argparse.ArgumentParser()
args_parser.add_argument('base_model', help='The path to the base model')
args_parser.add_argument('lora_weights', help='The path to the lora weights')
args_parser.add_argument('output_model', help='The path to the output model')
args = args_parser.parse_args()

tokenizer = LlamaTokenizer.from_pretrained(args.base_model)

base_model = LlamaForCausalLM.from_pretrained(
    args.base_model,
    load_in_8bit=False,
    torch_dtype=torch.float16,
    device_map={"": "cpu"},
)

first_weight = base_model.model.layers[0].self_attn.q_proj.weight
first_weight_old = first_weight.clone()

lora_model = PeftModel.from_pretrained(
    base_model,
    args.lora_weights,
    device_map={"": "cpu"},
    torch_dtype=torch.float16,
)

lora_weight = lora_model.base_model.model.model.layers[
    0
].self_attn.q_proj.weight

assert torch.allclose(first_weight_old, first_weight)

# merge weights - new merging method from peft
lora_model = lora_model.merge_and_unload()

lora_model.train(False)

# did we do anything?
assert not torch.allclose(first_weight_old, first_weight)

lora_model_sd = lora_model.state_dict()
deloreanized_sd = {
    k.replace("base_model.model.", ""): v
    for k, v in lora_model_sd.items()
    if "lora" not in k
}

LlamaForCausalLM.save_pretrained(
    base_model, args.output_model, state_dict=deloreanized_sd, max_shard_size="400MB"
)
