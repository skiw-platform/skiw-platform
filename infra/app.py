import aws_cdk as cdk

from skiw_infra.placeholder_stack import PlaceholderStack

app = cdk.App()
# Region comes from cdk.json context (spec D3). No account is named: nothing deploys until M1.
PlaceholderStack(app, "SkiwPlaceholder", env=cdk.Environment(region=app.node.get_context("region")))
app.synth()
