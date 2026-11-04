// (Probe) Read a CT .utest file with the FST library that CT ships, and print the object graph.
// Run by tools/java_probe.py with CT's own Java and a classpath of CT's jars. Java 8 syntax on purpose.
// Output lines (UTF-8, tab separated), read only by java_probe.py, never shown raw on screen:
//   TRY  <factory>  <exception chain>      a factory that could not read the file
//   OK   <FST class> <factory>             the factory that read it
//   N    <path> <type> <value>             one node of the graph
//   FAIL <exception chain>                 nothing could read it
import java.io.FileDescriptor;
import java.io.FileOutputStream;
import java.io.PrintStream;
import java.lang.reflect.Array;
import java.lang.reflect.Field;
import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Modifier;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.util.Collection;
import java.util.IdentityHashMap;
import java.util.Map;

public class UtestDump {
    static final String[] FST = {"org.nustaq.serialization.FSTConfiguration",
                                 "de.ruedigermoeller.serialization.FSTConfiguration"};
    static final String[] FACTORIES = {"createDefaultConfiguration", "createUnsafeBinaryConfiguration",
                                       "createStructConfiguration"};
    static final int MAX_NODES = 200000;
    static PrintStream out;
    static IdentityHashMap<Object, String> seen = new IdentityHashMap<Object, String>();
    static int nodes = 0;

    public static void main(String[] args) throws Exception {
        out = new PrintStream(new FileOutputStream(FileDescriptor.out), true, "UTF-8");
        byte[] data = Files.readAllBytes(Paths.get(args[0]));
        Throwable last = null;
        for (String name : FST) {
            Class<?> fst;
            try {
                fst = Class.forName(name);
            } catch (Throwable t) {
                continue;
            }
            for (String factory : FACTORIES) {
                try {
                    Object conf = fst.getMethod(factory).invoke(null);
                    Object root = fst.getMethod("asObject", byte[].class).invoke(conf, (Object) data);
                    out.println("OK\t" + name + "\t" + factory);
                    dump("", root);
                    return;
                } catch (Throwable t) {
                    last = t;
                    out.println("TRY\t" + factory + "\t" + chain(t));
                }
            }
        }
        out.println("FAIL\t" + (last == null ? "NoFSTClass" : chain(last)));
    }

    // Exception class names from outer to inner. A message is added only when it is a Java name.
    static String chain(Throwable t) {
        StringBuilder b = new StringBuilder();
        while (t != null) {
            if (t instanceof InvocationTargetException && t.getCause() != null) {
                t = t.getCause();
                continue;
            }
            b.append(t.getClass().getName());
            String m = t.getMessage();
            if (m != null && m.matches("[\\w.$/]+")) {
                b.append("(").append(m).append(")");
            }
            t = t.getCause();
            if (t != null) {
                b.append(" < ");
            }
        }
        return b.toString();
    }

    static void emit(String path, String type, String value) {
        nodes++;
        out.println("N\t" + path + "\t" + type + "\t" + value.replace('\t', ' ').replace('\n', ' ').replace('\r', ' '));
    }

    static void dump(String path, Object o) {
        if (nodes > MAX_NODES) {
            return;
        }
        if (o == null) {
            emit(path, "null", "null");
            return;
        }
        Class<?> c = o.getClass();
        if (o instanceof String) {
            emit(path, "String", (String) o);
            return;
        }
        if (o instanceof Number || o instanceof Boolean || o instanceof Character) {
            emit(path, c.getSimpleName(), String.valueOf(o));
            return;
        }
        if (o instanceof Enum) {
            emit(path, "enum " + ((Enum<?>) o).getDeclaringClass().getName(), ((Enum<?>) o).name());
            return;
        }
        if (seen.containsKey(o)) {
            emit(path, "ref", seen.get(o));
            return;
        }
        seen.put(o, path.isEmpty() ? "/" : path);
        if (c.isArray()) {
            int n = Array.getLength(o);
            emit(path, "array " + c.getComponentType().getName(), "len " + n);
            for (int i = 0; i < n; i++) {
                dump(path + "[" + i + "]", Array.get(o, i));
            }
            return;
        }
        if (o instanceof Collection) {
            emit(path, c.getName(), "size " + ((Collection<?>) o).size());
            int i = 0;
            for (Object e : (Collection<?>) o) {
                dump(path + "[" + (i++) + "]", e);
            }
            return;
        }
        if (o instanceof Map) {
            emit(path, c.getName(), "size " + ((Map<?, ?>) o).size());
            int i = 0;
            for (Map.Entry<?, ?> e : ((Map<?, ?>) o).entrySet()) {
                dump(path + "{" + i + "}k", e.getKey());
                dump(path + "{" + i + "}v", e.getValue());
                i++;
            }
            return;
        }
        String cn = c.getName();
        if (cn.startsWith("java.") || cn.startsWith("javax.") || cn.startsWith("sun.") || cn.startsWith("jdk.")) {
            emit(path, cn, "(jdk)");
            return;
        }
        emit(path, cn, "object");
        for (Class<?> k = c; k != null && k != Object.class; k = k.getSuperclass()) {
            for (Field f : k.getDeclaredFields()) {
                if (Modifier.isStatic(f.getModifiers())) {
                    continue;
                }
                try {
                    f.setAccessible(true);
                    dump(path + "." + f.getName(), f.get(o));
                } catch (Throwable t) {
                    emit(path + "." + f.getName(), "error", t.getClass().getSimpleName());
                }
            }
        }
    }
}
