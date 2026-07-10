# Repository Inventory
Date: 2026-07-10T18:27:19.741822

## Directory Structure
```
/root/aziza-build
├── archive
│   ├── backups
│   │   ├── finetune_moshi.py.bak
│   │   ├── finetune_moshi.py.bak2
│   │   ├── finetune_moshi.py.bak3
│   │   ├── start_vllm_uz.sh.bak
│   │   ├── train_uzbek_cyrillic_hf.py.bak
│   │   └── train_uzbek_latin_hf.py.bak
│   ├── deprecated
│   │   ├── =0.42.0
│   │   ├── =4.45.0
│   │   ├── artifacts
│   │   ├── AZIZA-PRODUCTION-BUILD
│   │   ├── chat.gateway.ts
│   │   ├── chat_template.jinja
│   │   ├── data
│   │   ├── lt_url.txt
│   │   ├── mcp
│   │   ├── outputs
│   │   ├── package.json
│   │   ├── package-lock.json
│   │   ├── requirements-vllm.txt
│   │   ├── telemetry
│   │   ├── tokenizer_audit.json
│   │   └── uzbek-tokenizer
│   ├── logs
│   │   ├── output_logs2.txt
│   │   ├── output_logs3.txt
│   │   ├── output_logs4.txt
│   │   ├── output_logs5.txt
│   │   ├── train_run_1783504371.log
│   │   ├── train_run_1783509539.log
│   │   ├── train_run_1783512725.log
│   │   ├── train_run.log
│   │   ├── train_run_uzbek_real_1783513532.log
│   │   └── train_run_uzbek_real_1783513836.log
│   ├── old-configs
│   └── old-training
├── backend
│   ├── api
│   ├── fine-tuning
│   │   ├── academic.jsonl
│   │   ├── audit_tokenizer_uz.py
│   │   ├── aziza-adapter-final-ru
│   │   ├── aziza-adapter-final-uz
│   │   ├── aziza-uzbek.jsonl
│   │   ├── benchmark_ttft.py
│   │   ├── bench_ttft.py
│   │   ├── colloquial.jsonl
│   │   ├── data
│   │   ├── data_academic
│   │   ├── data_colloquial
│   │   ├── data_professional
│   │   ├── data_uzbek
│   │   ├── en_ru_raw.jsonl
│   │   ├── eval_uzbek.py
│   │   ├── finetune_moshi.py
│   │   ├── finetune_moshi.py.bak
│   │   ├── generate_en_ru_dataset.py
│   │   ├── generate_synthetic_uzbek.py
│   │   ├── inspect_moshi.py
│   │   ├── list_repo.py
│   │   ├── prepare_dataset.py
│   │   ├── print_modules.py
│   │   ├── professional.jsonl
│   │   ├── requirements.txt
│   │   ├── run_curriculum_training.sh
│   │   ├── split_uzbek.py
│   │   ├── tokenizer_audit.py
│   │   ├── train_uzbek.py
│   │   └── validate_uzbek_dataset.py
│   ├── gateway
│   │   ├── ollama_proxy.py
│   │   ├── __pycache__
│   │   ├── serve_multilingual.py
│   │   ├── server.py
│   │   └── serve_russian_test.py
│   ├── infrastructure
│   │   ├── mongo
│   │   ├── monitoring
│   │   ├── nginx
│   │   └── redis
│   ├── persona-plex
│   │   ├── database.py
│   │   ├── Dockerfile
│   │   ├── main.py
│   │   ├── memory.py
│   │   ├── models.py
│   │   ├── persona_plex_core.py
│   │   ├── __pycache__
│   │   ├── requirements.txt
│   │   ├── startup.log
│   │   ├── test_mongo.py
│   │   └── uvicorn.log
│   ├── requirements.txt
│   ├── services
│   │   ├── admin-api
│   │   ├── api-gateway
│   │   ├── audit_tokenizer.py
│   │   ├── bench_ttft.py
│   │   ├── check_cuda_properties.py
│   │   ├── check_embedding_headroom.py
│   │   ├── check_monitor.py
│   │   ├── check_status.py
│   │   ├── e2e_sip_test.py
│   │   ├── extend_tokenizer_vocab.py
│   │   ├── find_text_embedding.py
│   │   ├── force_net.py
│   │   ├── generate_audio.py
│   │   ├── generate_uzbek_mock.py
│   │   ├── gen_pdf.py
│   │   ├── get_pip.py
│   │   ├── inspect_safetensors.py
│   │   ├── moshi-worker
│   │   ├── orchestrator
│   │   ├── patch_transformers.py
│   │   ├── patch_trl.py
│   │   ├── personaplex
│   │   ├── push_file.py
│   │   ├── query_storage_cluster.py
│   │   ├── query_storage.py
│   │   ├── realtime_demo.py
│   │   ├── recover_clean_checkpoint.py
│   │   ├── relaunch_russian.py
│   │   ├── remote_cmd.py
│   │   ├── remote_exec.py
│   │   ├── run_mongo_setup.py
│   │   ├── run_paramiko.py
│   │   ├── run_remote.py
│   │   ├── run_tests.py
│   │   ├── setup_cloudinit.py
│   │   ├── start_services.py
│   │   ├── streaming-runtime
│   │   ├── telephony
│   │   ├── test_complex_map.py
│   │   ├── test_emotion.py
│   │   ├── test_load2.py
│   │   ├── test_load.py
│   │   ├── test_mongo.py
│   │   ├── test_personaplex.py
│   │   ├── test_personaplex_restart.py
│   │   ├── test_persona.py
│   │   ├── test_remote_code.py
│   │   ├── test_russian.py
│   │   ├── test_tokenizer.py
│   │   ├── test_trace2.py
│   │   ├── test_trace.py
│   │   ├── test_ws.py
│   │   ├── type_cmd.py
│   │   └── voice_to_text_validation.py
│   ├── telephony-bridge
│   │   ├── main.py
│   │   └── requirements.txt
│   ├── tests
│   │   ├── e2e_sip_test.py
│   │   └── integration
│   ├── test_ws_direct_en.js
│   └── workers
├── benchmarks
│   ├── benchmark
│   │   ├── benchmark
│   │   ├── benchmark_config.yaml
│   │   ├── benchmark.py
│   │   ├── benchmark_results
│   │   ├── data
│   │   ├── DEPLOYMENT_GUIDE.md
│   │   ├── phonetic_benchmarks.jsonl
│   │   ├── phonetic_validation.py
│   │   ├── PR_SUMMARY.md
│   │   ├── README.md
│   │   ├── reports
│   │   ├── results
│   │   ├── run_benchmark.sh
│   │   ├── scripts
│   │   ├── setup_and_run.sh
│   │   ├── telemetry
│   │   └── test_audio.raw
│   ├── benchmark_config.yaml
│   ├── data
│   │   └── text_prompts.json
│   ├── DEPLOYMENT_GUIDE.md
│   ├── mock_gateway.py
│   ├── mock_gateway_remote.py
│   ├── PR_SUMMARY.md
│   ├── README.md
│   ├── reports
│   │   ├── e2e_integration.md
│   │   ├── final_report.json
│   │   ├── final_report.md
│   │   ├── Leon_Aziza_Benchmark_Report.md
│   │   ├── Leon_Aziza_Benchmark_Report.pdf
│   │   ├── stability.md
│   │   ├── text_to_text.md
│   │   ├── ttft.csv
│   │   ├── ttft.json
│   │   ├── ttft.md
│   │   ├── voice_roundtrip.md
│   │   └── voice_to_text.md
│   ├── scripts
│   │   ├── e2e_integration_test.py
│   │   ├── generate_report.py
│   │   ├── run_benchmarks.sh
│   │   ├── stability_test.py
│   │   ├── text_to_text_benchmark.py
│   │   ├── ttft_benchmark.py
│   │   ├── voice_roundtrip_benchmark.py
│   │   └── voice_to_text_validation.py
│   ├── setup_and_run.sh
│   ├── telemetry
│   │   ├── e2e_006857dc-3833-4e65-9a97-77d0573f57c1.json
│   │   ├── e2e_1d0d4e23-17c5-490b-8a77-19dbf1104d91.json
│   │   ├── e2e_23ce11c7-a4df-4574-9c5a-c4fedbc315ba.json
│   │   ├── e2e_23f33138-9cd0-4a69-aacf-95c21aae26cb.json
│   │   ├── e2e_279b4a08-cd8f-4cf9-8db8-1df6bacaeda2.json
│   │   ├── e2e_2abc7fc9-aaa7-44a0-b66d-93a1ac554f34.json
│   │   ├── e2e_2ac0b2d6-ba2e-4519-b4b3-ffb58836aa5e.json
│   │   ├── e2e_317f39df-6c59-44ee-be23-ae34fe3dedfe.json
│   │   ├── e2e_4502bff0-5fab-4b8c-83fa-bff773f6784e.json
│   │   ├── e2e_4eb64775-e4b4-4942-b7dc-6759d7badbb0.json
│   │   ├── e2e_54a905d3-f838-4016-85a8-016c310975a5.json
│   │   ├── e2e_5b65a1ae-ec02-4c78-9f70-aa89dfedd6f6.json
│   │   ├── e2e_63763a0b-896c-4a8e-a9b3-1f22de29add5.json
│   │   ├── e2e_655d34f8-931b-4ffe-913f-35377498b958.json
│   │   ├── e2e_6a265598-0021-4ecd-96e3-91d159442bc3.json
│   │   ├── e2e_70d78782-42ce-4644-97f0-18e7b63b74d1.json
│   │   ├── e2e_778b656f-4c98-408d-9e52-d5967c6bd65b.json
│   │   ├── e2e_77c94fbc-5f7f-4437-b2c2-cc312b6a40c9.json
│   │   ├── e2e_7bc12bf1-ac9a-46da-9fc0-00da946e2ab4.json
│   │   ├── e2e_827b339b-951c-4748-88f8-80647cf3f8f3.json
│   │   ├── e2e_84304d19-edc5-4f54-9a6c-5060a387cf5d.json
│   │   ├── e2e_a2a09928-4635-42bb-89c7-abae9c8ba96e.json
│   │   ├── e2e_b15a8b2d-c59f-45ce-a838-20e07b43aee0.json
│   │   ├── e2e_c21e9074-9872-4311-af0d-60d71776bdd3.json
│   │   ├── e2e_c7d729e3-6a72-481d-ba67-21bed3a3a381.json
│   │   ├── e2e_e1be1484-7fc8-4ae2-857c-0605f4616832.json
│   │   ├── e2e_e299ca74-03b2-47ea-8cb2-ffe13b7ab615.json
│   │   ├── e2e_fceb8446-4153-4f35-bb94-5d31e2408c30.json
│   │   ├── e2e_fd2c27f7-9c82-4f24-919c-bc549c76fd8c.json
│   │   ├── stability_08f21899-393a-4064-9971-4290893a24db.json
│   │   ├── stability_0944d55f-133f-4c33-87ee-0d413ecf7533.json
│   │   ├── stability_0bef2613-245b-4d31-9539-afa422836198.json
│   │   ├── stability_20b07103-9ce9-4061-930d-d715c8f6b0be.json
│   │   ├── stability_292c40fd-9814-462b-a9ec-d3869d8fb13b.json
│   │   ├── stability_385ea783-cd73-426a-bf81-9d96dcf1779c.json
│   │   ├── stability_3f3249f9-3a63-41e2-8edb-0b435d2dc8b0.json
│   │   ├── stability_445bc404-f737-44f8-bb64-8f708ebbab17.json
│   │   ├── stability_4d9c2469-c064-4ed0-bff3-746443e0f6ba.json
│   │   ├── stability_7df13ad6-dcb1-4b9c-9799-ae28167482bb.json
│   │   ├── stability_99e6423b-d1a8-42f0-8e38-0c3f2b0b8888.json
│   │   ├── stability_a493b452-a2c7-4a94-92bb-28a685bdc185.json
│   │   ├── stability_b225ac02-4dbf-4c42-869f-e5a50b212878.json
│   │   ├── stability_bd118d7f-fa65-45d8-a364-906ed8a30a3b.json
│   │   ├── stability_c3ceceeb-8d93-44ec-a7de-a0c6e77598eb.json
│   │   ├── stability_ed531a28-a092-4370-99de-f31509a86089.json
│   │   ├── stability_f813269b-0fe4-4e67-b810-80c62b33180b.json
│   │   ├── text_to_text_025acf91-20b7-46ed-b271-bce9ad8bff9a.json
│   │   ├── text_to_text_0b72a03d-dbfc-4ea5-9683-f9dbe554c408.json
│   │   ├── text_to_text_0bb8113a-6411-4208-904c-a5500c4ab146.json
│   │   ├── text_to_text_2b5d4a59-a4bb-4c60-ab82-fc2cd9b827b8.json
│   │   ├── text_to_text_2bcfeb34-0633-44b3-b345-63ada5599497.json
│   │   ├── text_to_text_3531f144-7404-40ae-941e-c130a4938554.json
│   │   ├── text_to_text_36230f51-a46b-42c5-8996-3bb52280d7d7.json
│   │   ├── text_to_text_3dd2951f-523a-4ea4-bb8f-3c76febb12e2.json
│   │   ├── text_to_text_44ff90fb-719f-4c90-9ba5-f38994e36550.json
│   │   ├── text_to_text_583b316d-4822-416a-85a9-458489bbd72f.json
│   │   ├── text_to_text_5e085225-88c3-4636-8183-2800c681dcdb.json
│   │   ├── text_to_text_737270a5-4490-4f85-8354-a60d50e96822.json
│   │   ├── text_to_text_7a4a5daa-2deb-4af2-b231-36b668f831db.json
│   │   ├── text_to_text_83dba3d4-93b0-4052-9c3d-372488db461f.json
│   │   ├── text_to_text_8d567dd7-70af-4c0c-91cd-1ee1534bffce.json
│   │   ├── text_to_text_93ec889d-7822-43d9-8702-66ac6a122062.json
│   │   ├── text_to_text_94e9a1d8-751b-47f4-ae6b-58b546f78b47.json
│   │   ├── text_to_text_aa319da0-08ac-41f4-b944-5d6ed6d591f5.json
│   │   ├── text_to_text_abe33531-4904-41ed-b17f-4b0cad7f8010.json
│   │   ├── text_to_text_b8cfeb3d-e008-44be-885a-72c6f90f30f7.json
│   │   ├── text_to_text_b9d13e96-1a39-477e-915e-23efedeb5c5e.json
│   │   ├── text_to_text_bbdd7753-a330-4e6c-a0f7-cd60697a6695.json
│   │   ├── text_to_text_ebbd6a48-11de-42da-9414-f9a085750b69.json
│   │   ├── text_to_text_f446b43b-6784-4063-ab6c-ff126bf02d51.json
│   │   ├── text_to_text_fd5f8bd5-7a27-4ff7-8c67-cfad2d187140.json
│   │   ├── ttft_0844f86e-7e70-4d49-a716-c7db464931a7.json
│   │   ├── ttft_0dad9990-2ac1-4d46-b814-63499c26c9ad.json
│   │   ├── ttft_0fbda11e-8d34-4f55-973e-b999f1d43b23.json
│   │   ├── ttft_12727f6a-f9d4-4cbd-8a9a-c038ba14f6cc.json
│   │   ├── ttft_211a5642-ef31-4f63-82eb-3f48eb6ad6db.json
│   │   ├── ttft_322d495c-213b-4ab4-8041-7fde572b310a.json
│   │   ├── ttft_43767823-5681-4089-99ac-dff712cc0c9d.json
│   │   ├── ttft_43a46bd9-2da8-4f66-97ce-9438867e542e.json
│   │   ├── ttft_4ff9246c-c4be-4f14-9e26-168815efd4a6.json
│   │   ├── ttft_7827fe43-d085-415e-8562-81fbce24d753.json
│   │   ├── ttft_7c44f3ce-683f-4da7-ada5-400b574ec0f4.json
│   │   ├── ttft_816e58dc-befb-433f-97c0-ab86409df2eb.json
│   │   ├── ttft_8864befd-0662-4858-8b64-2548f64805da.json
│   │   ├── ttft_98cc79fc-be5b-411b-aff7-5bc49a46281a.json
│   │   ├── ttft_bdd86cf9-9bf4-4249-9540-75f3150c7cf5.json
│   │   ├── ttft_bf25c953-e605-47f3-83fe-961d01321b5a.json
│   │   ├── ttft_c5f51464-5c0d-4e7a-9854-ab65b681a422.json
│   │   ├── ttft_c8d19b51-d350-47c0-a84e-20d1d0a0acfe.json
│   │   ├── ttft_ced587c5-ee64-49d9-b815-c8d2eec34667.json
│   │   ├── ttft_d33b1139-45e1-492b-aa75-27611317c641.json
│   │   ├── ttft_da12bc7b-05af-4af4-bb90-3b0f5d83a580.json
│   │   ├── ttft_da2780ca-b599-47a4-b018-799cc9ce7b0b.json
│   │   ├── ttft_dcd9ed61-6b7a-4b8a-b4ee-029141a24071.json
│   │   ├── ttft_dd65ae63-79b6-4595-b47c-6038e34b9288.json
│   │   ├── ttft_de67a75f-3d94-495a-b103-0e011d649a5e.json
│   │   ├── ttft_f7587360-6ec0-4252-a5c0-27364cdb6e5c.json
│   │   ├── voice_roundtrip_0b21437a-0179-4c82-8d6a-333dc06ecda3.json
│   │   ├── voice_roundtrip_0e9a811a-b9ed-42f3-bdb1-29bcf4b94670.json
│   │   ├── voice_roundtrip_1c7303b2-1587-4fac-8d12-749e2cbeadfd.json
│   │   ├── voice_roundtrip_25eecad1-696d-4537-b87b-da1d29babae0.json
│   │   ├── voice_roundtrip_319751a6-b7b7-4665-9597-09fb08cb4f0b.json
│   │   ├── voice_roundtrip_36a1b2d6-3e28-4c0f-b32b-7f9d142d2cc3.json
│   │   ├── voice_roundtrip_39bd5e01-f3ef-4c25-8549-8fcdfad04e34.json
│   │   ├── voice_roundtrip_48f8b92a-78e5-4c49-93b2-f810c68f1ab5.json
│   │   ├── voice_roundtrip_62472553-ce31-4623-9b71-1c2b4b7d4f06.json
│   │   ├── voice_roundtrip_646cff48-d66a-4a59-89f2-a5124095c87b.json
│   │   ├── voice_roundtrip_69fb69dc-a968-40e3-ba92-26e80c99aca6.json
│   │   ├── voice_roundtrip_8094311e-82f9-4f2a-a418-a42efb2bf264.json
│   │   ├── voice_roundtrip_88c65173-04b9-4824-b784-314a72fc3491.json
│   │   ├── voice_roundtrip_9b15bc54-9d53-425f-9a8b-41a1957f0db0.json
│   │   ├── voice_roundtrip_aaff15b1-ecad-4c62-9d59-1034979ba27d.json
│   │   ├── voice_roundtrip_b6dad126-8068-491b-91e3-fe1c3423eb1f.json
│   │   ├── voice_roundtrip_b7c48588-74e5-4d01-90d5-04fbb07b7826.json
│   │   ├── voice_roundtrip_b93a7333-90b5-4c7a-8293-c0d2c7a856a1.json
│   │   ├── voice_roundtrip_d4ccb089-3b60-4456-b55c-2fc6f731cd30.json
│   │   ├── voice_roundtrip_e67dced8-f264-44be-8e70-863ed5d93dd3.json
│   │   ├── voice_roundtrip_f1c99aec-20c5-4eb1-bf14-e0f5d6d3d453.json
│   │   ├── voice_to_text_0de4e93d-f623-4203-94a3-50fadfef3bd2.json
│   │   ├── voice_to_text_1056ab95-d52d-4810-95f7-f13cfa3aca13.json
│   │   ├── voice_to_text_106ce0f7-dc18-4bc9-8596-8d34449c0a81.json
│   │   ├── voice_to_text_1c10ca68-9a6b-4d52-8bbf-fc14448212bd.json
│   │   ├── voice_to_text_1ca39046-9a67-4ec0-8dc4-d86512eb3c3b.json
│   │   ├── voice_to_text_1da0c3c2-683e-45c1-b3e9-6072620aa7dc.json
│   │   ├── voice_to_text_24348ae6-f65b-408a-a75a-905db54086c1.json
│   │   ├── voice_to_text_2c292588-a0f9-4007-be9e-095fd89dc9db.json
│   │   ├── voice_to_text_36858129-ae7f-4404-b4b7-16d4544c3df7.json
│   │   ├── voice_to_text_36ada2cc-9e48-4c76-8b16-682fd0d71b45.json
│   │   ├── voice_to_text_568505b0-2efa-4b95-82ad-96cfed690b2e.json
│   │   ├── voice_to_text_71830bce-3bfb-4346-90b3-3d8d4f5fec2f.json
│   │   ├── voice_to_text_72329094-2e93-44c4-b42f-4abcbb53cfec.json
│   │   ├── voice_to_text_8609dfcf-60fd-4551-8ffd-996bbe177ade.json
│   │   ├── voice_to_text_8b0a6073-c8d6-42e9-a972-37f87a4cfbd0.json
│   │   ├── voice_to_text_94be840a-406f-4d87-ac08-186f1fb4a3a6.json
│   │   ├── voice_to_text_9da3c743-8471-42a3-a58f-26f766e8e49d.json
│   │   ├── voice_to_text_a92a2249-f4b9-4304-9401-e33c2187adb5.json
│   │   ├── voice_to_text_ac670eb7-1ce4-4cd5-86a0-01d9e93d14db.json
│   │   ├── voice_to_text_b6cbd086-9df9-49fc-991c-d19362829d23.json
│   │   ├── voice_to_text_bc8f56e9-7bb4-4599-9b93-f2cdf73cac94.json
│   │   ├── voice_to_text_e4db26af-5bad-4072-bcb5-d4ef1c54d2a3.json
│   │   ├── voice_to_text_e4ff8ac6-24a8-4ef9-8162-952d3652582b.json
│   │   ├── voice_to_text_e5919cfb-9a57-48ee-b69b-c1f89844cad5.json
│   │   └── voice_to_text_fa655afa-c670-47a3-af6d-09e08f2a4b96.json
│   └── voice_to_text_validation.py
├── configs
│   ├── docker
│   │   ├── benchmark_config.yaml
│   │   └── docker-compose.yml
│   ├── env_backups
│   │   ├── remote.env.bak
│   │   ├── root.env.bak
│   │   └── root.env.example.bak
│   ├── nginx
│   │   └── nginx
│   ├── ollama
│   │   ├── Modelfile.aziza
│   │   ├── Modelfile.aziza-t2t
│   │   └── Modelfile.aziza-vikhr
│   ├── pm2
│   │   ├── aziza.config.js
│   │   ├── ecosystem.config.js
│   │   ├── ecosystem-temp.config.js
│   │   └── remote_ecosystem.config.js
│   └── vllm
│       └── vllm.config.js
├── deployment
│   ├── adapter
│   │   ├── adapter.service
│   │   ├── push-package.ps1
│   │   ├── push.ps1
│   │   └── README.md
│   ├── add_key.exp
│   ├── apply_remote_nginx.exp
│   ├── ari-bridge
│   │   ├── ari-bridge.service
│   │   └── README.md
│   ├── asterisk-gateway
│   │   ├── extensions.conf
│   │   ├── pjsip.conf
│   │   ├── pjsip.secrets.conf
│   │   ├── pjsip.secrets.conf.example
│   │   ├── push.ps1
│   │   ├── README.md
│   │   └── rtp.conf
│   ├── astpp
│   │   └── README.md
│   ├── aziza-web
│   │   ├── aziza-web.service
│   │   ├── env.example
│   │   ├── install.sh
│   │   └── README.md
│   ├── check_nvidia.exp
│   ├── check_pm2.exp
│   ├── check_proxmox.py
│   ├── check_ssh.py
│   ├── cloudflare
│   ├── cloudflared
│   ├── deploy_and_train_aziza.py
│   ├── deploy_and_train.py
│   ├── deploy_and_train_root.py
│   ├── deploy_frontend.exp
│   ├── deploy_gateway.py
│   ├── deploy_new_server.exp
│   ├── deploy_rsync.py
│   ├── deploy_server.py
│   ├── deploy.sh
│   ├── deploy_to_vast.sh
│   ├── dialogue-engine
│   │   ├── env.example
│   │   ├── install.sh
│   │   ├── README.md
│   │   └── telephony-llm.service
│   ├── get_vast.py
│   ├── get_vast_ssh.py
│   ├── get_vm_ip.py
│   ├── kamailio
│   │   ├── etc-default-kamailio
│   │   ├── kamailio.cfg
│   │   ├── kamctlrc
│   │   ├── push.ps1
│   │   └── README.md
│   ├── proxmox
│   ├── reboot_vm.py
│   ├── run_eval.exp
│   ├── run_ssh_cmd.py
│   ├── server
│   ├── ssh
│   ├── ssh_aziza.exp
│   ├── ssh_remote.exp
│   ├── ssh_run.py
│   ├── start_vm.py
│   ├── systemd
│   ├── test_ssh.exp
│   ├── test_ssh_pers.exp
│   ├── test_ssh_root.exp
│   ├── update_remote_gateway.exp
│   ├── vast
│   ├── vitalpbx-asterisk
│   │   ├── ari_amd.conf
│   │   ├── extensions_amd.conf
│   │   ├── include_extensions_custom.snippet
│   │   ├── pjsip_TRUNK_01.reference.conf
│   │   └── README.md
│   ├── vm_config.py
│   └── vps
│       ├── bootstrap.sh
│       ├── deploy-all.sh
│       ├── push-sources.ps1
│       └── README.md
├── docs
│   ├── api
│   ├── architecture
│   ├── AZIZA-BUILD.md
│   ├── AZIZA-REVISED-PHASES.md
│   ├── CLAUDE.md
│   ├── DEPLOY.md
│   ├── pdf
│   │   ├── Aziza_Benchmark_Report_Leon.pdf
│   │   ├── AZIZA-RUSSIAN-TEST-PLAN.pdf
│   │   └── milestone_new.pdf
│   ├── reports
│   │   ├── aziza_progress_report.md
│   │   └── reports
│   ├── SESSION_PROGRESS.md
│   └── training
├── engineering
│   ├── AGENT_RESPONSIBILITIES.md
│   ├── AI_WORKFLOW.md
│   ├── ARCHITECTURE_FREEZE.md
│   ├── ARCHITECTURE.md
│   ├── BACKLOG.md
│   ├── baseline
│   ├── BUILD.md
│   ├── CHANGELOG.md
│   ├── CURRENT_TASK.md
│   ├── DECISIONS.md
│   ├── DEPENDENCY_GRAPH.md
│   ├── DEPLOYMENT.md
│   ├── DEVELOPMENT_CHARTER.md
│   ├── DEVELOPMENT_WORKFLOW.md
│   ├── ENGINEERING_RULES.md
│   ├── FILE_INDEX.md
│   ├── FILE_MOVE_REPORT.md
│   ├── GITIGNORE_SUGGESTIONS.md
│   ├── GOVERNANCE.md
│   ├── GSD_GUIDE.md
│   ├── history
│   │   ├── 2026-07-10-session-001.md
│   │   ├── 2026-07-10-session-002.md
│   │   └── 2026-07-11-session-001.md
```

## Major Components
- **Backend:** `backend/`
- **Frontend:** `frontend/`
- **Training:** `training/`
- **Deployment:** `docker/`, `deployment/`
- **Configuration:** `configs/`
- **Benchmarks:** `benchmarks/`
- **Engineering Docs:** `engineering/`
