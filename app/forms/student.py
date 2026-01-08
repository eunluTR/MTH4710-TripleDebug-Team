from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SubmitField
from wtforms.validators import DataRequired, Length, Email


class ClubApplicationForm(FlaskForm):
    proposed_name = StringField("Proposed Club Name", validators=[DataRequired(), Length(max=200)])
    proposed_description = TextAreaField("Description", validators=[DataRequired()])
    proposed_category = StringField("Category", validators=[Length(max=120)])
    founders_note = TextAreaField("Founders Note")
    submit = SubmitField("Submit Application")


class FounderInviteForm(FlaskForm):
    invited_email = StringField("Founder Email", validators=[DataRequired(), Email()])
    submit = SubmitField("Invite Founder")


class MembershipApplicationForm(FlaskForm):
    message = TextAreaField("Message")
    submit = SubmitField("Apply")


class SimpleSubmitForm(FlaskForm):
    submit = SubmitField("Submit")
