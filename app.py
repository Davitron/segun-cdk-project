#!/usr/bin/env python3

import aws_cdk as cdk
from stacks.swisscom_assessment.swisscom_assessment_stack import SwisscomAssessmentStack


app = cdk.App()
SwisscomAssessmentStack(app, "SwisscomAssessmentStack")

app.synth()
