from __future__ import annotations

import atexit
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path


JAVA_17_MODULE_OPTIONS = [
    "-XX:+IgnoreUnrecognizedVMOptions",
    "--add-opens=java.base/java.lang=ALL-UNNAMED",
    "--add-opens=java.base/java.lang.invoke=ALL-UNNAMED",
    "--add-opens=java.base/java.lang.reflect=ALL-UNNAMED",
    "--add-opens=java.base/java.io=ALL-UNNAMED",
    "--add-opens=java.base/java.net=ALL-UNNAMED",
    "--add-opens=java.base/java.nio=ALL-UNNAMED",
    "--add-opens=java.base/java.util=ALL-UNNAMED",
    "--add-opens=java.base/java.util.concurrent=ALL-UNNAMED",
    "--add-opens=java.base/java.util.concurrent.atomic=ALL-UNNAMED",
    "--add-opens=java.base/jdk.internal.ref=ALL-UNNAMED",
    "--add-opens=java.base/sun.nio.ch=ALL-UNNAMED",
    "--add-opens=java.base/sun.nio.cs=ALL-UNNAMED",
    "--add-opens=java.base/sun.security.action=ALL-UNNAMED",
    "--add-opens=java.base/sun.util.calendar=ALL-UNNAMED",
    "--add-opens=java.security.jgss/sun.security.krb5=ALL-UNNAMED",
    "-Djdk.reflect.useDirectMethodHandle=false",
]


def launch_gateway_direct(conf=None, popen_kwargs=None):
    """Launch Spark's Py4J gateway without Windows ``cmd.exe`` batch parsing.

    Spark's standard ``spark-submit.cmd`` round-trips the Java command through
    the active console code page.  That corrupts non-ASCII installation paths
    and can split paths containing spaces.  Passing an argument list directly
    to ``CreateProcessW`` keeps every path Unicode-safe and properly delimited.
    """

    from py4j.clientserver import ClientServer, JavaParameters, PythonParameters
    from py4j.java_gateway import GatewayParameters, JavaGateway, java_import
    from pyspark.errors import PySparkRuntimeError
    from pyspark.serializers import UTF8Deserializer, read_int

    if "PYSPARK_GATEWAY_PORT" in os.environ:
        gateway_port = int(os.environ["PYSPARK_GATEWAY_PORT"])
        gateway_secret = os.environ["PYSPARK_GATEWAY_SECRET"]
        proc = None
    else:
        spark_home = Path(os.environ["SPARK_HOME"])
        java_home = Path(os.environ["JAVA_HOME"])
        java_executable = java_home / "bin" / "java.exe"
        classpath = os.pathsep.join(
            [str(spark_home / "conf"), str(spark_home / "jars" / "*")]
        )
        conf_items = list(conf.getAll()) if conf else []
        conf_map = dict(conf_items)
        driver_memory = conf_map.get("spark.driver.memory", "2g")
        command = [
            str(java_executable),
            "-cp",
            classpath,
            f"-Xmx{driver_memory}",
            *JAVA_17_MODULE_OPTIONS,
            "org.apache.spark.deploy.SparkSubmit",
        ]
        for key, value in conf_items:
            command.extend(["--conf", f"{key}={value}"])
        command.append("pyspark-shell")

        conn_info_dir = tempfile.mkdtemp(prefix="urban-flow-pyspark-")
        conn_info_file = Path(conn_info_dir) / "gateway.info"
        env = dict(os.environ)
        env["_PYSPARK_DRIVER_CONN_INFO_PATH"] = str(conn_info_file)
        kwargs = dict(popen_kwargs or {})
        kwargs["stdin"] = subprocess.PIPE
        kwargs["env"] = env
        kwargs.setdefault("creationflags", subprocess.CREATE_NO_WINDOW)
        proc = subprocess.Popen(command, **kwargs)
        try:
            deadline = time.monotonic() + 60
            while (
                proc.poll() is None
                and not conn_info_file.is_file()
                and time.monotonic() < deadline
            ):
                time.sleep(0.1)
            if not conn_info_file.is_file():
                return_code = proc.poll()
                if return_code is None:
                    proc.kill()
                raise PySparkRuntimeError(
                    error_class="JAVA_GATEWAY_EXITED",
                    message_parameters={},
                )
            with conn_info_file.open("rb") as info:
                gateway_port = read_int(info)
                gateway_secret = UTF8Deserializer().loads(info)
        finally:
            shutil.rmtree(conn_info_dir, ignore_errors=True)

        def kill_child() -> None:
            if proc.poll() is None:
                subprocess.Popen(
                    ["taskkill", "/f", "/t", "/pid", str(proc.pid)],
                    creationflags=subprocess.CREATE_NO_WINDOW,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )

        atexit.register(kill_child)

    if os.environ.get("PYSPARK_PIN_THREAD", "true").lower() == "true":
        gateway = ClientServer(
            java_parameters=JavaParameters(
                port=gateway_port, auth_token=gateway_secret, auto_convert=True
            ),
            python_parameters=PythonParameters(port=0, eager_load=False),
        )
    else:
        gateway = JavaGateway(
            gateway_parameters=GatewayParameters(
                port=gateway_port, auth_token=gateway_secret, auto_convert=True
            )
        )
    gateway.proc = proc

    java_import(gateway.jvm, "org.apache.spark.SparkConf")
    java_import(gateway.jvm, "org.apache.spark.api.java.*")
    java_import(gateway.jvm, "org.apache.spark.api.python.*")
    java_import(gateway.jvm, "org.apache.spark.ml.python.*")
    java_import(gateway.jvm, "org.apache.spark.mllib.api.python.*")
    java_import(gateway.jvm, "org.apache.spark.resource.*")
    java_import(gateway.jvm, "org.apache.spark.sql.*")
    java_import(gateway.jvm, "org.apache.spark.sql.api.python.*")
    java_import(gateway.jvm, "org.apache.spark.sql.hive.*")
    java_import(gateway.jvm, "scala.Tuple2")
    return gateway
