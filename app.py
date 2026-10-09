#!/usr/bin/env python3
import os
import aws_cdk as cdk
from infrastructure.gridshift_stack import GridShiftStack

app = cdk.App()
GridShiftStack(app, "GridShiftAws", env=cdk.Environment(
    account=os.environ.get("CDK_DEFAULT_ACCOUNT"),
    region=os.environ.get("CDK_DEFAULT_REGION", "ap-south-1"),
))
app.synth()
