# Orca 개발 흐름

**트바 마스터** Claude 세션(Opus)에 아이디어나 작업을 자연어로 맡깁니다. 마스터는 [오케스트레이션 절차](../../.claude/skills/orchestrate/SKILL.md)에 따라 개발 작업자(Claude Sonnet, 노력치 medium)에게 구현을 맡기고, 중요한 결정에만 승인을 요청합니다. 독립 리뷰는 모든 변경에 Codex(gpt-6.2-sol, high)와 Claude(Sonnet, high)를 서로의 결과를 보지 못하게 병렬로 돌리고, 마스터가 두 보고를 병합해 판단합니다. 이미지·아이콘 같은 그래픽 자산은 Codex(gpt-6.2-sol, high) 작업자가 만듭니다. 역할별 값은 오케스트레이션 절차의 표가 기준입니다.

## 트바 마스터 열기

Orca 사이드바에서 **Local Mac → TB → 트바 마스터**의 기존 Claude 채팅을 엽니다. 채팅 탭을 닫았다면 해당 워크트리의 **에이전트 세션 기록**에서 `트바 마스터`를 재개합니다. 터미널에서도 워크트리를 열 수 있습니다. Orca가 꺼져 있으면 먼저 `orca open`을 실행합니다.

```sh
orca worktree activate --environment local --worktree 'branch:orca/coordinator'
```

마스터에 목표를 한 문장으로 보내면 됩니다. 구체적인 완료 조건이 이미 있다면 함께 적습니다.

```text
/orchestrate 방문 인증 배지가 있는 리뷰와 없는 리뷰를 구분해 보여줘.
```

기존 마스터 채팅에서 새 요청을 받으면 [로컬 main 동기화](#로컬-main-동기화)를 실행하고 최신 작성 규칙과 마스터 절차를 읽습니다.

마스터 채팅을 처음부터 만들 때만 아래 명령을 사용합니다. 첫 프롬프트는 준비 확인만 요청하므로, 응답을 받은 뒤 작업을 보냅니다.

```sh
orca agent launch --environment local --worktree 'branch:orca/coordinator' \
  --agent claude --model claude-opus-5-5 --effort high --surface chat --focus \
  --prompt '트바 마스터로 준비해줘. CLAUDE.md와 AGENTS.md, /orchestrate 절차를 읽고 준비됐다고 알려줘. 작업 실행은 내 다음 요청부터 시작해줘.'
```

## 작업부터 병합까지

아래 순서는 수동으로 작업할 때도 적용할 수 있습니다.

1. Orca의 **Local Mac**에서 이 Git 저장소를 열고, 작업 목표와 요구사항 ID, 인수 기준을 정리합니다. 기능 단위로 GitHub Issue를 연결할 수 있습니다.
2. 독립적으로 진행할 변경은 기능마다 별도 브랜치와 Orca worktree를 사용합니다. 같은 파일을 수정해야 하는 작업은 순서를 정합니다.
3. 개발 작업은 변경 범위와 검증 결과를 남깁니다. 병렬로 실행할 경우 각 작업에 담당 범위와 기준 브랜치를 명시합니다.
4. 별도 리뷰 세션이나 Claude Code `reviewer`에 기준 브랜치, diff, 인수 기준, 검증 결과를 넘깁니다. 리뷰어가 확인한 문제를 개발 세션에서 고치고 관련 검사를 다시 실행합니다.
5. [커밋·이슈·PR 작성 규칙](PR-ISSUE-GUIDE.md)에 맞춰 Draft PR을 올립니다. 마스터는 최종 커밋의 Claude·Codex 완료 보고 두 건을 [병합 스크립트](../../scripts/orca_merge.py)로 검증합니다. GitHub에서 `TB CI`, `tb/review-claude`, `tb/review-codex`가 통과해야 squash 병합됩니다. 하네스·권한·CI·판정 기준·운영 DB 마이그레이션 변경과 제품 결정이 남은 PR은 사람의 확인을 받습니다. 첫 실기기 테스트에서 기기 조작이 필요한 시점에 iPhone 연결을 요청합니다.

두 독립 리뷰의 판정이나 중요한 지적이 갈리면 마스터가 양쪽 근거를 정리해 Claude와 Codex에 같은 쟁점을 보냅니다. 먼저 병합 실행기로 Draft PR 번호와 최종 SHA의 재검토 Run을 등록한 뒤 두 리뷰를 시작합니다. 병합 실행기는 그 Run의 재검토 `PASS` 두 건을 요구합니다. 쟁점이 해소된 근거와 최종 판정은 PR에 남깁니다.

## 로컬 main 동기화

마스터는 GitHub에서 PR 병합을 확인한 뒤와 새 요청을 시작하기 전에 트바 마스터 worktree에서 아래 명령을 실행합니다. GitHub 웹에서 직접 병합한 변경도 다음 요청을 시작할 때 반영합니다.

```sh
/opt/homebrew/bin/tb-orca-merge --sync-main
```

실행기는 `origin/main`의 한 커밋을 기준으로 로컬 `main`과 `orca/coordinator`를 각각 fast-forward합니다. 다른 worktree가 쓰는 `main`은 해당 폴더에서 갱신합니다. 미커밋 변경, 로컬 커밋 또는 Git의 안전 검사에 걸린 브랜치는 그 상태를 남깁니다. `orca/coordinator`가 동기화되지 않으면 마스터가 원인을 보고하고 새 작업 시작을 보류합니다. 로컬 `main`만 보류됐으면 마스터와 새 작업자의 기준은 확인된 `origin/main`을 사용합니다.

## 사용량 한도와 작업 재개

Orca의 **설정 → 채팅 UI → 사용 한도가 재설정되면 채팅을 자동으로 계속하기**를 켜고 Claude·Codex 모두 채팅으로 실행합니다. 같은 맥에서 Orca와 해당 채팅이 열려 있고 Orca가 한도 재설정을 감지하면 마지막 작업을 이어갑니다. 마스터가 대기 상태인 동안에도 사용 가능한 워커의 작업 결과는 같은 Run에 남습니다.

재설정 정보를 확인할 수 없거나 실패가 채팅 시작 전에 발생하면 Orca 자동 재개가 예약되지 않을 수 있습니다. 여러 번의 자동 재개가 한도에 막히면 Orca의 재개 횟수 상한에 도달할 수도 있습니다. 이때는 [사용량 한도 복구 절차](../../.claude/skills/orchestrate/SKILL.md#사용량-한도에서-재개)로 기존 Run·Task와 작업물을 확인한 뒤 이어갑니다. 맥이 잠들거나 Orca가 종료되면 그동안에는 재개가 실행되지 않습니다.

## 앱을 만든 뒤 연결할 항목

- `README.md`에 재현 가능한 설치, 실행, 검증 명령을 추가합니다.
- 프로젝트가 생성한 코드와 파일 배치를 기준으로 고정된 규칙이 필요한 곳에 `.claude/rules/`를 둡니다.
- 초기 CI는 문서 diff와 병합 스크립트를 검사합니다. 앱 생성 후 같은 CI가 Node 24와 npm 잠금 파일로 린트·타입 검사·테스트를 실행하게 `package.json`에 명령을 정의합니다. `/verify`에도 실제 검증 명령을 기록합니다. 오케스트레이션 권한(Orca 명령, 읽기 전용 git, 비밀 경로 읽기 거부)은 `.claude/settings.json`에 미리 적용했습니다. `.claude/`와 `REVIEW.md`는 Edit·Write 도구에 승인 프롬프트(ask)를 걸어 두었습니다. Bash를 통한 쓰기와 허용한 읽기 전용 git의 우회는 이 규칙으로 막지 못하므로 리뷰에서 "판정 기준 변경"으로 걸러내며, 단계 0에서 샌드박스 적용과 실제 동작을 확인합니다(R-27). 앱 스크립트(`npm run lint/typecheck/test`) 권한은 앱 초기화 뒤 실제 스크립트에 맞춰 좁히고, 훅은 필요한 시점에 추가합니다.
- iOS 앱 화면은 [테스트 전략](../quality/TEST-STRATEGY.md#iphone-연결-상태에-따른-검증)에 따라 연결된 iPhone에서 Mobile MCP를 우선 사용합니다. iPhone이 없어도 자동 검사·독립 리뷰·CI는 진행합니다. 필수 실기기 검사가 남은 PR은 Draft에서 기다리고, [실기기 체크리스트](../quality/RELIABILITY-CHECKLIST.md)를 실행할 준비가 됐을 때 연결을 요청합니다.

## 마스터 병합 실행기 (맥에 1회 설치)

마스터는 절대 경로에 설치된 `/opt/homebrew/bin/tb-orca-merge`만 호출합니다. 설치와 갱신은 검토를 마치고 보호된 `origin/main`에 병합된 버전의 `scripts/orca_merge.py`로 진행합니다. 작업 브랜치의 스크립트를 GitHub 쓰기 권한으로 실행하지 않습니다. Mac을 바꾸거나 그 파일을 변경한 운영 PR을 병합했으면 새 버전을 다시 설치합니다.

이견 재검토를 등록하면 실행기가 해당 SHA에 `tb/recheck-registered` 상태로 PR 링크와 Orca Run ID를 기록합니다. GitHub의 필수 상태는 SHA에 붙으므로, 같은 SHA로 다른 PR을 열어도 등록을 적용합니다. 등록과 병합 요청은 GitHub의 임시 `tb-review-lock/<SHA>` 브랜치로 동시에 한 실행기만 처리하며 실행 뒤 잠금을 해제합니다. 두 필수 리뷰 판정은 별도로 게시합니다. 맥을 바꿔 재개할 때도 GitHub에서 등록한 Run을 확인합니다. 그 Run의 기록을 복원할 수 없거나 기존 SHA의 승인 게시 뒤에 새 이견이 생기면 새 검토 대상 커밋으로 리뷰를 다시 시작합니다.

중단이나 통신 오류로 잠금이 남으면 먼저 GitHub에서 PR이 병합됐거나 자동 병합 대기 중인지 확인합니다. 같은 SHA를 처리하던 모든 실행기가 종료됐고 잠금 브랜치가 그 SHA를 가리키는 것을 확인한 뒤, 저장소 소유자가 해당 `tb-review-lock/<SHA>` 브랜치만 삭제합니다. 열린 Draft 작업은 기존 GitHub 등록과 Orca Run에서 검토를 이어갑니다.

GitHub Actions가 이름이 `TB CI`인 검사를 게시합니다. Claude·Codex 판정은 마스터의 GitHub 계정으로 별개의 커밋 상태에 게시하며, Orca 작업자 두 명의 완료 기록과 최종 SHA를 대조합니다. 리뷰 공급자 두 곳이 GitHub에 각각 로그인하는 방식은 사용하지 않습니다.

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
