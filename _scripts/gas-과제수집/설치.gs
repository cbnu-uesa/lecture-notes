/**
 * 손으로 돌리는 함수들.
 *
 * Apps Script 편집기 위쪽 함수 목록에서 골라 실행한다.
 * 결과는 「실행 로그」에 찍힌다.
 */

/**
 * 과제 제출 폼을 만든다. **학기에 한 번만 돌린다.**
 *
 * 질문 넷 중 셋을 스크립트가 넣는다. **파일 업로드 질문만은 못 넣는다** —
 * Apps Script 의 Form 클래스에 add...Item() 이 열일곱 개 있는데 그것만 없다.
 * 실행이 끝나면 편집 주소를 찍어 준다. 거기서 질문 하나만 추가하면 끝이다.
 *
 * 이미 폼이 있으면 돌리지 않는다 — 주차를 더할 때는 주차항목갱신() 을 쓴다.
 */
function 폼만들기() {
  const form = FormApp.create('데이터사이언스 과제 제출');
  form.setDescription(
    '주차를 고르고 과제 파일을 올립니다.\n' +
    '학번과 이름은 제출물이 담길 폴더 이름이 되므로 정확히 적습니다.\n' +
    '한 학기 동안 이 주소 하나를 씁니다.');
  form.setAllowResponseEdits(false); // 수정하면 파일이 갈린다
  form.setProgressBar(false);

  // 이메일 수집 — 구글이 「확인됨 / 응답자 입력」 둘로 나눈 뒤 API 가 갈렸다.
  // 새 쪽을 먼저 시도하고 없으면 옛 쪽으로 켠다.
  try {
    form.setEmailCollectionType(FormApp.EmailCollectionType.VERIFIED);
  } catch (err) {
    try { form.setCollectEmail(true); } catch (err2) {
      console.warn('이메일 수집을 못 켰다. 폼 설정에서 손으로 켠다 — ' + err2);
    }
  }

  form.addListItem()
    .setTitle(Q.주차)
    .setHelpText('고른 값이 그대로 폴더 이름이 됩니다')
    .setChoiceValues(주차목록)
    .setRequired(true);

  const 검증 = FormApp.createTextValidation()
    .setHelpText('학번 ' + 학번자릿수 + '자리를 숫자만 적습니다')
    .requireTextMatchesPattern('^\\d{' + 학번자릿수 + '}$')
    .build();
  form.addTextItem().setTitle(Q.학번).setRequired(true).setValidation(검증);
  form.addTextItem().setTitle(Q.이름).setRequired(true);
  form.addParagraphTextItem()
    .setTitle('하고 싶은 말')
    .setHelpText('막힌 곳 · 질문 · 덧붙일 설명. 비워 두어도 됩니다')
    .setRequired(false);

  try {
    DriveApp.getFileById(form.getId()).moveTo(DriveApp.getFolderById(ROOT_FOLDER_ID));
  } catch (err) {
    console.warn('루트 폴더로 못 옮겼다. 내 드라이브 맨 위에 있다 — ' + err);
  }

  console.log('폼을 만들었다.');
  console.log('설정.gs 의 폼_ID 에 이 값을 넣는다: ' + form.getId());
  console.log('');
  console.log('▶ 손으로 할 일 하나 — 아래 주소를 열어');
  console.log('  「파일 업로드」 질문을 추가하고 필수로 둔 뒤, 「하고 싶은 말」 위로 끌어 올린다.');
  console.log('  (스크립트는 파일 질문을 제목이 아니라 유형으로 찾으므로 제목은 아무거나 좋다)');
  console.log('  ' + form.getEditUrl());
  console.log('');
  console.log('그다음 트리거설치() 를 돌리고, 아래 주소를 학생에게 알린다.');
  console.log('  ' + form.getPublishedUrl());
}

/**
 * 이미 있는 폼에 주차 드롭다운을 맞춘다.
 * 설정.gs 의 주차목록을 고친 뒤 돌린다. 질문이 없으면 새로 만들어 맨 위에 둔다.
 */
function 주차항목갱신() {
  if (자리표시자(폼_ID)) { console.error('설정.gs 의 폼_ID 를 먼저 채운다'); return; }
  const form = FormApp.openById(폼_ID);

  const 있는것 = form.getItems(FormApp.ItemType.LIST)
    .filter(function (i) { return i.getTitle().trim() === Q.주차; });

  if (있는것.length) {
    있는것[0].asListItem().setChoiceValues(주차목록).setRequired(true);
    console.log('주차 드롭다운을 갱신했다 (' + 주차목록.length + '개 항목)');
  } else {
    const item = form.addListItem()
      .setTitle(Q.주차)
      .setHelpText('고른 값이 그대로 폴더 이름이 됩니다')
      .setChoiceValues(주차목록)
      .setRequired(true);
    form.moveItem(item.getIndex(), 0);   // 맨 위로
    console.log('주차 드롭다운을 새로 넣고 맨 위로 올렸다 (' + 주차목록.length + '개 항목)');
  }
  console.log('편집 주소: ' + form.getEditUrl());
}

/** 폼에 제출 트리거를 건다. 이미 걸려 있으면 아무것도 하지 않는다. */
function 트리거설치() {
  if (자리표시자(폼_ID)) { console.error('설정.gs 의 폼_ID 를 먼저 채운다'); return; }

  const 이미 = ScriptApp.getProjectTriggers().some(function (t) {
    return t.getHandlerFunction() === 'onSubmit' && t.getTriggerSourceId() === 폼_ID;
  });
  if (이미) { console.log('이미 걸려 있다. 할 일 없음'); return; }

  const form = FormApp.openById(폼_ID);   // 접근 권한을 여기서 먼저 확인한다
  ScriptApp.newTrigger('onSubmit').forForm(form).onFormSubmit().create();
  console.log('설치했다: ' + form.getTitle());
}

/** 이 프로젝트가 건 제출 트리거를 전부 지운다. */
function 트리거해제() {
  let n = 0;
  ScriptApp.getProjectTriggers().forEach(function (t) {
    if (t.getHandlerFunction() === 'onSubmit') { ScriptApp.deleteTrigger(t); n++; }
  });
  console.log('지운 트리거 ' + n + '개');
}

/**
 * 마감 뒤에 한 번 돌린다. 고치지 않고 보기만 한다.
 *
 *   - 제자리에 있지 않은 파일이 몇 개인지  ← 0 이어야 한다
 *   - 주차별로 누가 냈는지
 *   - 학번 자릿수가 다른 폴더 (오타 후보)
 */
function 점검() {
  if (자리표시자(폼_ID)) { console.error('설정.gs 의 폼_ID 를 먼저 채운다'); return; }
  const form = FormApp.openById(폼_ID);
  const 응답들 = form.getResponses();
  const 주차별 = {};
  let 어긋남 = 0, 사라짐 = 0, 못읽음 = 0;

  응답들.forEach(function (응답) {
    try {
      const 항목 = 응답.getItemResponses();
      const 주차명 = 주차확인(값(항목, Q.주차));
      const 폴더명 = 폴더이름(값(항목, Q.학번), 값(항목, Q.이름));
      if (!주차별[주차명]) 주차별[주차명] = {};
      주차별[주차명][폴더명] = (주차별[주차명][폴더명] || 0) + 1;

      const 기대 = 하위폴더(
        하위폴더(DriveApp.getFolderById(ROOT_FOLDER_ID), 주차명), 폴더명);

      항목
        .filter(function (ir) { return ir.getItem().getType() === FormApp.ItemType.FILE_UPLOAD; })
        .reduce(function (a, ir) { return a.concat(ir.getResponse() || []); }, [])
        .forEach(function (id) {
          try {
            if (!제자리인가(DriveApp.getFileById(id), 기대)) {
              어긋남++;
              console.warn('제자리 아님: ' + 주차명 + ' / ' + 폴더명 + ' — ' + id);
            }
          } catch (err) {
            사라짐++;
            console.warn('파일을 찾을 수 없음: ' + id);
          }
        });
    } catch (err) {
      못읽음++;
      console.error('응답을 읽을 수 없다 (' + 응답.getTimestamp() + ') — ' + err);
    }
  });

  console.log('응답 ' + 응답들.length + '건 · 제자리 아님 ' + 어긋남 + '개 · ' +
    '사라짐 ' + 사라짐 + '개 · 못 읽음 ' + 못읽음 + '건');
  const 학번꼴 = new RegExp('^\\d{' + 학번자릿수 + '}_');
  Object.keys(주차별).sort().forEach(function (주차명) {
    const 이름들 = Object.keys(주차별[주차명]).sort();
    console.log('── ' + 주차명 + ' ─ ' + 이름들.length + '명');
    이름들.forEach(function (n) {
      const 표 = 학번꼴.test(n) ? '   ' : ' ? ';   // ? 는 학번 자릿수가 다른 것 — 오타 후보
      console.log(표 + n + (주차별[주차명][n] > 1 ? '  (제출 ' + 주차별[주차명][n] + '회)' : ''));
    });
  });
  console.log('「제자리 아님」이 0 이 아니면 밀린것처리() 를 돌린다');
}

/**
 * 트리거가 죽어 있던 동안 밀린 제출을 뒤늦게 정리한다.
 * 이미 옮긴 것은 건드리지 않으므로 몇 번을 돌려도 안전하다.
 */
function 밀린것처리() {
  if (자리표시자(폼_ID)) { console.error('설정.gs 의 폼_ID 를 먼저 채운다'); return; }
  const form = FormApp.openById(폼_ID);
  let 옮김 = 0, 실패 = 0;
  form.getResponses().forEach(function (응답) {
    try {
      옮김 += 정리(응답).옮긴것.length;
    } catch (err) {
      실패++;
      console.error(응답.getTimestamp() + ' — ' + err);
    }
  });
  console.log('옮긴 파일 ' + 옮김 + '개 · 실패 ' + 실패 + '건');
}

/** 설정이 맞는지만 본다. 제출이 없어도 돌릴 수 있다. */
function 설정확인() {
  try {
    console.log('루트 폴더: ' + DriveApp.getFolderById(ROOT_FOLDER_ID).getName());
  } catch (err) {
    console.error('루트 폴더를 열 수 없다. ROOT_FOLDER_ID 를 확인한다 — ' + err);
    return;
  }
  console.log('학번 자릿수: ' + 학번자릿수 + ' · 주차목록 ' + 주차목록.length + '개');
  console.log('알림 받을 주소: ' + (알림받을주소 || Session.getEffectiveUser().getEmail()));

  if (자리표시자(폼_ID)) {
    console.error('폼_ID 가 비어 있다. 폼만들기() 를 돌리고 그 값을 넣는다');
    return;
  }
  let form;
  try {
    form = FormApp.openById(폼_ID);
  } catch (err) {
    console.error('폼을 열 수 없다. 폼_ID 를 확인한다 — ' + err);
    return;
  }

  const 제목들 = form.getItems().map(function (i) { return i.getTitle().trim(); });
  const 없는것 = [Q.주차, Q.학번, Q.이름].filter(function (t) { return 제목들.indexOf(t) < 0; });
  const 업로드 = form.getItems(FormApp.ItemType.FILE_UPLOAD).length;
  const 트리거 = ScriptApp.getProjectTriggers().some(function (t) {
    return t.getHandlerFunction() === 'onSubmit' && t.getTriggerSourceId() === 폼_ID;
  });

  console.log('폼: ' + form.getTitle() + ' · 응답 ' + form.getResponses().length + '건');
  console.log('  파일 질문 ' + 업로드 + '개' + (업로드 === 0 ? '  ← 손으로 하나 넣어야 한다' : ''));
  console.log('  트리거 ' + (트리거 ? '있음' : '없음  ← 트리거설치() 를 돌린다'));
  console.log('  응답 수집 ' + (form.isAcceptingResponses() ? '켜짐' : '꺼짐  ← 폼이 응답을 안 받는다'));
  if (없는것.length) console.error('  없는 질문: ' + 없는것.join(', '));

  const 목록 = form.getItems(FormApp.ItemType.LIST)
    .filter(function (i) { return i.getTitle().trim() === Q.주차; });
  if (목록.length) {
    const 항목 = 목록[0].asListItem().getChoices().map(function (c) { return c.getValue(); });
    const 빠진것 = 주차목록.filter(function (w) { return 항목.indexOf(w) < 0; });
    const 남는것 = 항목.filter(function (w) { return 주차목록.indexOf(w) < 0; });
    console.log('  주차 드롭다운 ' + 항목.length + '개' +
      (빠진것.length || 남는것.length ? '  ← 주차항목갱신() 을 돌린다' : ' · 설정과 일치'));
    if (빠진것.length) console.warn('    폼에 없는 주차: ' + 빠진것.join(', '));
    if (남는것.length) console.warn('    설정에 없는 주차: ' + 남는것.join(', '));
  }
  console.log('학생에게 줄 주소: ' + form.getPublishedUrl());
}
