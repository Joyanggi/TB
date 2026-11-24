# Orca 개발 흐름

**트바 마스터** Claude 세션(Opus)에 아이디어나 작업을 자연어로 맡깁니다. 마스터는 [오케스트레이션 절차](../../.claude/skills/orchestrate/SKILL.md)에 따라 개발 작업자(Claude Sonnet, 노력치 medium)에게 구현을 맡기고, 중요한 결정에만 승인을 요청합니다. 독립 리뷰는 모든 변경에 Codex(gpt-6.2-sol, high)와 Claude(Sonnet, high)를 서로의 결과를 보지 못하게 병렬로 돌리고, 마스터가 두 보고를 병합해 판단합니다. 이미지·아이콘 같은 그래픽 자산은 Codex(gpt-6.2-sol, high) 작업자가 만듭니다. 역할별 값은 오케스트레이션 절차의 표가 기준입니다.

아래 순서는 수동으로 작업할 때도 적용할 수 있습니다.

1. Orca의 **Local Mac**에서 이 Git 저장소를 열고, 작업 목표와 요구사항 ID, 인수 기준을 정리합니다. 기능 단위로 GitHub Issue를 연결할 수 있습니다.
2. 독립적으로 진행할 변경은 기능마다 별도 브랜치와 Orca worktree를 사용합니다. 같은 파일을 수정해야 하는 작업은 순서를 정합니다.
3. 개발 작업은 변경 범위와 검증 결과를 남깁니다. 병렬로 실행할 경우 각 작업에 담당 범위와 기준 브랜치를 명시합니다.
4. 별도 리뷰 세션이나 Claude Code `reviewer`에 기준 브랜치, diff, 인수 기준, 검증 결과를 넘깁니다. 리뷰어가 확인한 문제를 개발 세션에서 고치고 관련 검사를 다시 실행합니다.
5. [Issue·PR 작성 규칙](PR-ISSUE-GUIDE.md)의 양식으로 Draft PR을 올립니다. 마스터는 최종 커밋의 Claude·Codex 완료 보고 두 건을 [병합 스크립트](../../scripts/orca_merge.py)로 검증합니다. GitHub에서 `TB CI`, `tb/review-claude`, `tb/review-codex`가 통과해야 squash 병합됩니다. 하네스·권한·CI 변경과 제품 결정이 남은 PR은 사람의 확인을 받습니다. 첫 실기기 테스트에서 기기 조작이 필요한 시점에 iPhone 연결을 요청합니다.

## 앱을 만든 뒤 연결할 항목

- `README.md`에 재현 가능한 설치, 실행, 검증 명령을 추가합니다.
- 프로젝트가 생성한 코드와 파일 배치를 기준으로 고정된 규칙이 필요한 곳에 `.claude/rules/`를 둡니다.
- 초기 CI는 문서 diff와 병합 스크립트를 검사합니다. 앱 생성 후 같은 CI가 Node 24와 npm 잠금 파일로 린트·타입 검사·테스트를 실행하게 `package.json`에 명령을 정의합니다. `/verify`에도 실제 검증 명령을 기록합니다. 오케스트레이션 권한(Orca 명령, 읽기 전용 git, 비밀 경로 읽기 거부)은 `.claude/settings.json`에 미리 적용했습니다. `.claude/`와 `REVIEW.md`는 Edit·Write 도구에 승인 프롬프트(ask)를 걸어 두었습니다. Bash를 통한 쓰기와 허용한 읽기 전용 git의 우회는 이 규칙으로 막지 못하므로 리뷰에서 "판정 기준 변경"으로 걸러내며, 단계 0에서 샌드박스 적용과 실제 동작을 확인합니다(R-27). 앱 스크립트(`npm run lint/typecheck/test`) 권한은 앱 초기화 뒤 실제 스크립트에 맞춰 좁히고, 훅은 필요한 시점에 추가합니다.
- 개발 환경은 현재 맥의 자원을 고려해 진행합니다. 첫 iOS 빌드에서 실기기를 사용하고, 다른 기기나 시뮬레이터 설정은 그 검증 계획에 맞춰 추가합니다.

## Codex 작업자 설정 (저장소 밖, 1회)

Codex 작업자는 샌드박스 때문에 `orca orchestration send`(worker_done 보고)가 차단돼 매번 승인을 요구할 수 있습니다. 이를 막으려고 `~/.codex/rules/orca-orchestration.rules`에 아래 규칙을 둡니다. 이 파일은 개인 설정이라 저장소에 포함하지 않으며, 새 Mac에서는 다시 만들어야 합니다.

```starlark
prefix_rule(
    pattern = ["orca", "orchestration", "send"],
    decision = "allow",
    justification = "Orca worker reports to its coordinator",
)
prefix_rule(
    pattern = ["orca", "orchestration", "ask"],
    decision = "allow",
    justification = "Orca worker questions to its coordinator",
)
```

- 허용 범위는 `orca orchestration send`(수신자·유형을 가리지 않음)와 `orca orchestration ask`뿐입니다. 다른 `orca` 명령은 허용하지 않습니다.
- 확인: `codex execpolicy check --rules ~/.codex/rules/orca-orchestration.rules -- orca orchestration send --from t --type worker_done`가 `allow`를 반환해야 합니다.
- 2026-11-24에 적용 후 Codex 작업자(gpt-6.2-sol, high)가 승인 프롬프트 없이 `worker_done`을 보내는 것을 확인했습니다.
- 규칙이 없거나 동작하지 않으면 오케스트레이션 절차의 "Codex 보고 전달 막힘" 우회(마스터가 `worker-read`로 보고 확보)를 사용합니다.
