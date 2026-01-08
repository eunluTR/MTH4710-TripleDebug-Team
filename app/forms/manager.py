from flask_wtf import FlaskForm
from wtforms import (
    StringField,
    TextAreaField,
    SubmitField,
    SelectField,
    IntegerField,
    DateTimeField,
)
from wtforms.validators import DataRequired, Length, Optional, Email, NumberRange, ValidationError


class ClubProfileForm(FlaskForm):
    name = StringField("Club Name", validators=[DataRequired(), Length(max=200)])
    description = TextAreaField("Description", validators=[DataRequired()])
    category = StringField("Category", validators=[Length(max=120)])
    logo_url = StringField("Logo URL", validators=[Optional(), Length(max=255)])
    contact_email = StringField("Contact Email", validators=[Optional(), Email()])
    submit = SubmitField("Save")


class MembershipDecisionForm(FlaskForm):
    decision = SelectField(
        "Decision",
        choices=[("approve", "Approve"), ("reject", "Reject")],
        validators=[DataRequired()],
    )
    decision_reason = TextAreaField("Reason", validators=[Optional()])
    submit = SubmitField("Submit")


class AnnouncementForm(FlaskForm):
    title = StringField("Title", validators=[DataRequired(), Length(max=200)])
    body = TextAreaField("Body", validators=[DataRequired()])
    submit = SubmitField("Post Announcement")


class EventProposalForm(FlaskForm):
    title = StringField("Title", validators=[DataRequired(), Length(max=200)])
    description = TextAreaField("Description", validators=[DataRequired()])
    location = StringField("Location", validators=[DataRequired(), Length(max=200)])
    start_datetime = DateTimeField(
        "Start (YYYY-MM-DD HH:MM)",
        validators=[DataRequired()],
        format="%Y-%m-%d %H:%M",
    )
    end_datetime = DateTimeField(
        "End (YYYY-MM-DD HH:MM)",
        validators=[DataRequired()],
        format="%Y-%m-%d %H:%M",
    )
    capacity = IntegerField("Capacity", validators=[Optional(), NumberRange(min=1)])
    registration_deadline = DateTimeField(
        "Registration Deadline (YYYY-MM-DD HH:MM)",
        validators=[Optional()],
        format="%Y-%m-%d %H:%M",
    )
    submit = SubmitField("Submit Proposal")

    def validate_end_datetime(self, field):
        if self.start_datetime.data and field.data and field.data <= self.start_datetime.data:
            raise ValidationError("End time must be after the start time.")

    def validate_registration_deadline(self, field):
        if self.start_datetime.data and field.data and field.data >= self.start_datetime.data:
            raise ValidationError("Registration deadline must be before the start time.")
