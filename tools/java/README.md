# CT Java 도우미

CT에 든 Java(서버 PC는 21.0.4, 컴파일러 없음)와 CT의 jar(FST 2.45, CT 모델)로 `.utest`를 다루는 Java 프로그램이다.
서버 PC에서는 컴파일할 수 없어(2026-11-04 todo.md 26절) 에이전트 PC에서 컴파일한 `.class`를 함께 커밋한다.

| 파일 | 하는 일 |
| --- | --- |
| `UtestDump.java` | (조사용) FST로 `.utest`를 읽어 객체 그래프를 찍는다. `tools/java_probe.py`가 부른다 |
| `UtestDump.class` | 위를 Java 11 바이트코드로 컴파일한 것 |
| `UtestDump.sha256` | `.class`를 만든 소스의 SHA-256. 단위 테스트가 소스와 맞는지 본다 |

소스를 고치면 JDK 11 이상으로 다시 컴파일하고 해시를 고친다. 저장소 루트에서:

```bat
javac --release 11 -encoding UTF-8 -d tools\java tools\java\UtestDump.java
python -c "import hashlib;print(hashlib.sha256(open('tools/java/UtestDump.java','rb').read()).hexdigest())" > tools\java\UtestDump.sha256
```

`.class`는 Git의 줄 끝 변환을 받지 않도록 `.gitattributes`에서 바이너리로 둔다.
