from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SelectField, SubmitField
from wtforms.validators import DataRequired, Email, Length, Optional


class ClubDecisionForm(FlaskForm):
    decision = SelectField(
        "Decision",
        choices=[("approve", "Approve"), ("reject", "Reject")],
        validators=[DataRequired()],
    )
    admin_comment = TextAreaField("Comment", validators=[Optional()])
    club_email = StringField("Club Email", validators=[Optional(), Email(), Length(max=255)])
    initial_password = StringField("Initial Password", validators=[Optional(), Length(min=8)])
    submit = SubmitField("Submit Decision")


class EventDecisionForm(FlaskForm):
    decision = SelectField(
        "Decision",
        choices=[("approve", "Approve"), ("reject", "Reject")],
        validators=[DataRequired()],
    )
    admin_comment = TextAreaField("Comment", validators=[Optional()])
    submit = SubmitField("Submit Decision")
