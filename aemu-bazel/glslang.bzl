"""Bazel rule for compiling GLSL shaders into SPIR-V C headers."""

def _glslang_spv_header_impl(ctx):
    args = ctx.actions.args()
    args.add("-V")
    for include in ctx.files.includes:
        args.add("-I" + include.dirname)
    args.add_all(ctx.attr.args)
    args.add("-o", ctx.outputs.out)
    args.add(ctx.file.src)

    ctx.actions.run(
        mnemonic = "GlslangSpvHeader",
        progress_message = "Compiling SPIR-V header %{output}",
        executable = ctx.executable._glslang,
        arguments = [args],
        inputs = depset([ctx.file.src] + ctx.files.srcs + ctx.files.includes),
        outputs = [ctx.outputs.out],
    )
    return [DefaultInfo(files = depset([ctx.outputs.out]))]

glslang_spv_header = rule(
    implementation = _glslang_spv_header_impl,
    attrs = {
        "args": attr.string_list(),
        "includes": attr.label_list(allow_files = True),
        "out": attr.output(mandatory = True),
        "src": attr.label(allow_single_file = True, mandatory = True),
        "srcs": attr.label_list(allow_files = True),
        "_glslang": attr.label(
            default = Label("@glslang//:glslangValidator"),
            executable = True,
            cfg = "exec",
        ),
    },
)
